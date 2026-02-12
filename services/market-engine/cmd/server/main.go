package main

import (
	"context"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/redis/go-redis/v9"
	"github.com/shopspring/decimal"

	"github.com/atmx/market-engine/internal/correlation"
	"github.com/atmx/market-engine/internal/metrics"
	"github.com/atmx/market-engine/internal/store"
	"github.com/atmx/market-engine/internal/trade"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	slog.SetDefault(logger)

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	// --- Initialize store ---
	var st store.Store
	var cleanup []func()

	if dbURL := os.Getenv("DATABASE_URL"); dbURL != "" {
		pool, err := pgxpool.New(context.Background(), dbURL)
		if err != nil {
			slog.Error("database connection failed", "err", err)
			os.Exit(1)
		}
		cleanup = append(cleanup, pool.Close)
		st = store.NewPostgresStore(pool)
		slog.Info("connected to PostgreSQL")

		// Wrap with Redis read-through cache if configured.
		if redisURL := os.Getenv("REDIS_URL"); redisURL != "" {
			opt, err := redis.ParseURL(redisURL)
			if err != nil {
				slog.Error("invalid REDIS_URL", "err", err)
				os.Exit(1)
			}
			rdb := redis.NewClient(opt)
			cleanup = append(cleanup, func() { rdb.Close() })
			st = store.NewCachedStore(st, rdb, 30*time.Second)
			slog.Info("Redis cache enabled")
		}
	} else {
		slog.Warn("DATABASE_URL not set, using in-memory store (data will not persist)")
		st = store.NewMemoryStore()
	}

	defer func() {
		for _, fn := range cleanup {
			fn()
		}
	}()

	// --- Position limits ---
	maxPerCell := decimal.NewFromInt(1000)
	maxCorrelated := decimal.NewFromInt(5000)
	prefixLen := 5 // hurricane-scale correlation radius
	limiter := correlation.NewPositionLimiter(maxPerCell, maxCorrelated, prefixLen)

	// --- WebSocket hub ---
	wsHub := trade.NewWSHub()
	go wsHub.Run()

	// --- Trade service ---
	tradeSvc := trade.NewService(st, limiter, wsHub)

	// --- HTTP router ---
	r := chi.NewRouter()
	r.Use(middleware.Logger)
	r.Use(middleware.Recoverer)
	r.Use(middleware.RequestID)
	r.Use(middleware.RealIP)
	r.Use(middleware.Timeout(30 * time.Second))
	r.Use(metrics.Middleware)

	// CORS middleware for frontend cross-origin requests.
	r.Use(func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			w.Header().Set("Access-Control-Allow-Origin", "*")
			w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
			if r.Method == "OPTIONS" {
				w.WriteHeader(http.StatusNoContent)
				return
			}
			next.ServeHTTP(w, r)
		})
	})

	r.Get("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":"ok","service":"market-engine"}`))
	})

	// Prometheus metrics endpoint.
	r.Handle("/metrics", metrics.Handler())

	r.Route("/api/v1", func(r chi.Router) {
		// WebSocket endpoint for real-time price updates.
		r.Get("/ws", wsHub.HandleWS)

		// Market management.
		r.Get("/markets", tradeSvc.ListMarkets)
		r.Post("/markets", tradeSvc.CreateMarket)
		r.Get("/markets/{marketID}", tradeSvc.GetMarket)
		r.Get("/markets/{marketID}/price", tradeSvc.GetPrice)
		r.Get("/markets/{marketID}/history", tradeSvc.GetMarketHistory)

		// Trade execution.
		r.Post("/trade", tradeSvc.ExecuteTrade)

		// Portfolio queries.
		r.Get("/portfolio/{userID}", tradeSvc.GetPortfolio)
	})

	// --- Server ---
	srv := &http.Server{
		Addr:         ":" + port,
		Handler:      r,
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 10 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	go func() {
		slog.Info("market-engine listening", "port", port)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			slog.Error("server error", "err", err)
			os.Exit(1)
		}
	}()

	// Graceful shutdown.
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	slog.Info("shutting down market-engine...")
	if err := srv.Shutdown(ctx); err != nil {
		slog.Error("shutdown error", "err", err)
	}
	fmt.Println("market-engine stopped")
}
