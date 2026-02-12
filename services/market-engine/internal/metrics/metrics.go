// Package metrics provides Prometheus instrumentation for the market engine.
package metrics

import (
	"net/http"
	"strconv"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
	// TradesTotal counts total trades executed, partitioned by side.
	TradesTotal = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "atmx_trades_total",
		Help: "Total number of trades executed",
	}, []string{"side"})

	// TradesPerSecond is a summary of trade execution rate.
	TradeLatency = promauto.NewHistogramVec(prometheus.HistogramOpts{
		Name:    "atmx_trade_latency_seconds",
		Help:    "Trade execution latency in seconds",
		Buckets: prometheus.DefBuckets,
	}, []string{"side"})

	// ActiveMarkets tracks the number of open markets.
	ActiveMarkets = promauto.NewGauge(prometheus.GaugeOpts{
		Name: "atmx_active_markets",
		Help: "Number of currently open markets",
	})

	// WebSocketClients tracks connected WebSocket clients.
	WebSocketClients = promauto.NewGauge(prometheus.GaugeOpts{
		Name: "atmx_websocket_clients",
		Help: "Number of connected WebSocket clients",
	})

	// HTTPRequestsTotal counts HTTP requests by method, path, and status.
	HTTPRequestsTotal = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "atmx_http_requests_total",
		Help: "Total HTTP requests",
	}, []string{"method", "path", "status"})

	// HTTPRequestDuration tracks request duration by method and path.
	HTTPRequestDuration = promauto.NewHistogramVec(prometheus.HistogramOpts{
		Name:    "atmx_http_request_duration_seconds",
		Help:    "HTTP request duration in seconds",
		Buckets: []float64{0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0},
	}, []string{"method", "path"})

	// PositionLimitRejections counts trades rejected by the position limiter.
	PositionLimitRejections = promauto.NewCounter(prometheus.CounterOpts{
		Name: "atmx_position_limit_rejections_total",
		Help: "Trades rejected by position limiter",
	})

	// MarketVolume tracks cumulative trade volume (quantity) per market.
	MarketVolume = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "atmx_market_volume_total",
		Help: "Cumulative trade volume in shares",
	}, []string{"market_id", "side"})
)

// Handler returns the Prometheus metrics HTTP handler.
func Handler() http.Handler {
	return promhttp.Handler()
}

// Middleware returns an HTTP middleware that records request metrics.
func Middleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		wrapped := &statusWriter{ResponseWriter: w, status: 200}
		next.ServeHTTP(wrapped, r)
		duration := time.Since(start).Seconds()

		// Use the route pattern for path label to avoid high cardinality.
		path := r.URL.Path
		HTTPRequestsTotal.WithLabelValues(r.Method, path, strconv.Itoa(wrapped.status)).Inc()
		HTTPRequestDuration.WithLabelValues(r.Method, path).Observe(duration)
	})
}

// statusWriter wraps http.ResponseWriter to capture the status code.
type statusWriter struct {
	http.ResponseWriter
	status int
}

func (w *statusWriter) WriteHeader(code int) {
	w.status = code
	w.ResponseWriter.WriteHeader(code)
}
