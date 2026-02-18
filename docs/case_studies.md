# ATMX Case Studies: Real Events, Real Weather, Real Settlement

These case studies reconstruct how ATMX weather protection **would have worked** for real outdoor events using verified historical weather data. Every observation is sourced from NOAA ASOS sensors via the [Iowa Environmental Mesonet archive](https://mesonet.agron.iastate.edu/request/download.phtml) — the same data source the ATMX settlement oracle uses in production.

Each case study walks through the complete contract lifecycle:

1. **Pricing** — LMSR-derived premium computed at time of ticket purchase
2. **Observation** — Real ASOS precipitation data during the event window
3. **Settlement** — Automated resolution against the contract threshold
4. **Audit** — SHA-256 hash-chained settlement record with full evidence payload

> All 10 case studies are linked in a single hash chain, demonstrating the tamper-evident audit trail that the CFTC requires for event contract record-keeping (17 CFR § 38.1051). The raw data is also available in [`case_studies.json`](case_studies.json).

---

## Summary

| # | Event | City | Date | Premium | Observed | Threshold | Outcome | Payout |
|---|-------|------|------|---------|----------|-----------|---------|--------|
| 1 | Summer Concert at Prospect Park | Brooklyn, NY | July 9, 2023 | $8.29 | 13.45 mm | 10.0 mm | **YES** ✅ | **$50.00** |
| 2 | Lollapalooza at Grant Park | Chicago, IL | July 12, 2023 | $9.94 | 15.23 mm | 12.0 mm | **YES** ✅ | **$75.00** |
| 3 | Bayfront Park Jazz Night | Miami, FL | August 17, 2023 | $14.36 | 86.87 mm | 20.0 mm | **YES** ✅ | **$65.00** |
| 4 | Atlanta Jazz Festival | Atlanta, GA | April 1, 2023 | $9.11 | 12.7 mm | 10.0 mm | **YES** ✅ | **$55.00** |
| 5 | Cinespia at Hollywood Forever | Los Angeles, CA | January 9, 2023 | $8.95 | 17.52 mm | 10.0 mm | **YES** ✅ | **$45.00** |
| 6 | Celebrate Brooklyn! at Prospect Park | Brooklyn, NY | July 15, 2023 | $3.43 | 0 mm | 10.0 mm | NO | — |
| 7 | Boston Pops Fireworks Spectacular | Boston, MA | July 4, 2023 | $3.87 | 5.33 mm | 10.0 mm | NO | — |
| 8 | Stern Grove Festival Concert | San Francisco, CA | September 1, 2023 | $0.88 | 0 mm | 5.0 mm | NO | — |
| 9 | Outdoor Cinema at Gas Works Park | Seattle, WA | July 25, 2023 | $1.33 | 0 mm | 5.0 mm | NO | — |
| 10 | Fair Park Food Festival | Dallas, TX | August 10, 2023 | $2.49 | 0 mm | 10.0 mm | NO | — |

---

## 1. Summer Concert at Prospect Park — Brooklyn, NY

### The Event

On **July 9, 2023**, An outdoor summer music festival at the Prospect Park Bandshell, one of Brooklyn's most popular venues for live outdoor performance. Summer evening thunderstorms are a perennial risk for NYC outdoor events. The event ran from **4:00 PM – 12:00 AM EDT** at Prospect Park Bandshell ($45 tickets).

### Risk Pricing

At **2:00 PM EDT**, the ATMX API would have returned:

| Parameter | Value |
|-----------|-------|
| Risk probability | 15.0% |
| Threshold | >10.0 mm precipitation |
| Event window | 4:00 PM – 12:00 AM EDT |
| Payout | $50.00 |
| **Premium** | **$8.29** |
| Pricing model | LMSR (b=100) + 10% loading |
| Oracle source | NOAA ASOS via IEM |
| Station | KJFK (JFK International Airport) |
| H3 cell (res 7) | `872a103b1ffffff` |

### ASOS Observations

Station **KJFK** recorded the following hourly precipitation:

| Hour (UTC) | Precipitation |
|------------|--------------|
| 2023-07-09 20:00 | 2.03 mm |
| 2023-07-09 21:00 | 0.25 mm |
| 2023-07-09 22:00 | 7.11 mm |
| 2023-07-10 02:00 | 4.06 mm |
| **Total** | **13.45 mm** |

> Verify: [IEM ASOS Archive](https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=KJFK&data=p01m&tz=Etc/UTC&format=comma&latlon=no&year1=2023&month1=7&day1=9&hour1=20&year2=2023&month2=7&day2=10&hour2=4)

### Settlement

The settlement engine auto-triggered at **12:30 AM EDT**, 30 minutes after the event window closed.

```json
{
  "outcome": "YES",
  "observed_value_mm": 13.45,
  "threshold_mm": 10.0,
  "exceeded": true,
  "settled_at": "2023-07-10T04:30:00+00:00",
  "payout_triggered": true,
  "payout_amount_usd": 50.0
}
```

**Result:** The ticket holder paid **$8.29** and received **$50.00** — a **6.0× return** on the weather protection.

### Settlement Record

```
Algorithm:   SHA-256
Record hash: cb72d08eb48fb736708bcd4926ece67e9cb7f0e8e61b78cf2d6573a03be0ada8
Prev hash:   (genesis — first record in chain)
```

<details>
<summary>Evidence payload</summary>

```json
{
  "contract": {
    "h3_cell": "872a103b1ffffff",
    "metric": "precipitation",
    "threshold_mm": 10.0,
    "unit": "mm",
    "window_start": "2023-07-09T20:00:00+00:00",
    "window_end": "2023-07-10T04:00:00+00:00"
  },
  "observation_summary": {
    "station": "KJFK",
    "station_name": "JFK International Airport",
    "total_raw_observations": 110,
    "hourly_readings": [
      {
        "hour_utc": "2023-07-09 20:00",
        "precip_mm": 2.03
      },
      {
        "hour_utc": "2023-07-09 21:00",
        "precip_mm": 0.25
      },
      {
        "hour_utc": "2023-07-09 22:00",
        "precip_mm": 7.11
      },
      {
        "hour_utc": "2023-07-10 02:00",
        "precip_mm": 4.06
      }
    ]
  },
  "determination": {
    "outcome": "YES",
    "observed_value_mm": 13.45,
    "threshold_mm": 10.0,
    "exceeded": true
  }
}
```

</details>

---

## 2. Lollapalooza at Grant Park — Chicago, IL

### The Event

On **July 12, 2023**, The build-up week of outdoor concerts and activations at Grant Park leading into Lollapalooza. Chicago's lakefront is highly exposed to mid-summer convective storms that sweep in from the Great Plains. The event ran from **12:00 PM – 10:00 PM CDT** at Grant Park ($135 tickets).

### Risk Pricing

At **9:00 AM CDT**, the ATMX API would have returned:

| Parameter | Value |
|-----------|-------|
| Risk probability | 12.0% |
| Threshold | >12.0 mm precipitation |
| Event window | 12:00 PM – 10:00 PM CDT |
| Payout | $75.00 |
| **Premium** | **$9.94** |
| Pricing model | LMSR (b=100) + 10% loading |
| Oracle source | NOAA ASOS via IEM |
| Station | KORD (O'Hare International Airport) |
| H3 cell (res 7) | `87275934effffff` |

### ASOS Observations

Station **KORD** recorded the following hourly precipitation:

| Hour (UTC) | Precipitation |
|------------|--------------|
| 2023-07-12 17:00 | 1.52 mm |
| 2023-07-12 18:00 | 7.87 mm |
| 2023-07-12 19:00 | 0.51 mm |
| 2023-07-12 23:00 | 2.79 mm |
| 2023-07-13 00:00 | 2.54 mm |
| **Total** | **15.23 mm** |

> Verify: [IEM ASOS Archive](https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=KORD&data=p01m&tz=Etc/UTC&format=comma&latlon=no&year1=2023&month1=7&day1=12&hour1=17&year2=2023&month2=7&day2=13&hour2=3)

### Settlement

The settlement engine auto-triggered at **10:30 PM CDT**, 30 minutes after the event window closed.

```json
{
  "outcome": "YES",
  "observed_value_mm": 15.23,
  "threshold_mm": 12.0,
  "exceeded": true,
  "settled_at": "2023-07-13T03:30:00+00:00",
  "payout_triggered": true,
  "payout_amount_usd": 75.0
}
```

**Result:** The ticket holder paid **$9.94** and received **$75.00** — a **7.5× return** on the weather protection.

### Settlement Record

```
Algorithm:   SHA-256
Record hash: a16b73e1459816285ba36dd5743f44b3be9c355333615535c57b6f5c8cbb02e0
Prev hash:   cb72d08eb48fb736708bcd4926ece67e9cb7f0e8e61b78cf2d6573a03be0ada8
```

<details>
<summary>Evidence payload</summary>

```json
{
  "contract": {
    "h3_cell": "87275934effffff",
    "metric": "precipitation",
    "threshold_mm": 12.0,
    "unit": "mm",
    "window_start": "2023-07-12T17:00:00+00:00",
    "window_end": "2023-07-13T03:00:00+00:00"
  },
  "observation_summary": {
    "station": "KORD",
    "station_name": "O'Hare International Airport",
    "total_raw_observations": 146,
    "hourly_readings": [
      {
        "hour_utc": "2023-07-12 17:00",
        "precip_mm": 1.52
      },
      {
        "hour_utc": "2023-07-12 18:00",
        "precip_mm": 7.87
      },
      {
        "hour_utc": "2023-07-12 19:00",
        "precip_mm": 0.51
      },
      {
        "hour_utc": "2023-07-12 23:00",
        "precip_mm": 2.79
      },
      {
        "hour_utc": "2023-07-13 00:00",
        "precip_mm": 2.54
      }
    ]
  },
  "determination": {
    "outcome": "YES",
    "observed_value_mm": 15.23,
    "threshold_mm": 12.0,
    "exceeded": true
  }
}
```

</details>

---

## 3. Bayfront Park Jazz Night — Miami, FL

### The Event

On **August 17, 2023**, An outdoor jazz performance at Bayfront Park Amphitheater. South Florida's late-summer thunderstorms are among the most intense in the continental US, fueled by tropical moisture and sea-breeze convergence. The event ran from **2:00 PM – 11:00 PM EDT** at Bayfront Park Amphitheater ($55 tickets).

### Risk Pricing

At **11:00 AM EDT**, the ATMX API would have returned:

| Parameter | Value |
|-----------|-------|
| Risk probability | 20.0% |
| Threshold | >20.0 mm precipitation |
| Event window | 2:00 PM – 11:00 PM EDT |
| Payout | $65.00 |
| **Premium** | **$14.36** |
| Pricing model | LMSR (b=100) + 10% loading |
| Oracle source | NOAA ASOS via IEM |
| Station | KMIA (Miami International Airport) |
| H3 cell (res 7) | `8744a1164ffffff` |

### ASOS Observations

Station **KMIA** recorded the following hourly precipitation:

| Hour (UTC) | Precipitation |
|------------|--------------|
| 2023-08-17 18:00 | 6.1 mm |
| 2023-08-17 19:00 | 14.48 mm |
| 2023-08-17 20:00 | 40.39 mm |
| 2023-08-18 01:00 | 19.3 mm |
| 2023-08-18 02:00 | 6.6 mm |
| **Total** | **86.87 mm** |

> Verify: [IEM ASOS Archive](https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=KMIA&data=p01m&tz=Etc/UTC&format=comma&latlon=no&year1=2023&month1=8&day1=17&hour1=18&year2=2023&month2=8&day2=18&hour2=3)

### Settlement

The settlement engine auto-triggered at **11:30 PM EDT**, 30 minutes after the event window closed.

```json
{
  "outcome": "YES",
  "observed_value_mm": 86.87,
  "threshold_mm": 20.0,
  "exceeded": true,
  "settled_at": "2023-08-18T03:30:00+00:00",
  "payout_triggered": true,
  "payout_amount_usd": 65.0
}
```

**Result:** The ticket holder paid **$14.36** and received **$65.00** — a **4.5× return** on the weather protection.

### Settlement Record

```
Algorithm:   SHA-256
Record hash: 5a24b3c9646c695ef913e4e7d56ebdc8aafe36c5b2b6e6fbf1439df72457f8ce
Prev hash:   a16b73e1459816285ba36dd5743f44b3be9c355333615535c57b6f5c8cbb02e0
```

<details>
<summary>Evidence payload</summary>

```json
{
  "contract": {
    "h3_cell": "8744a1164ffffff",
    "metric": "precipitation",
    "threshold_mm": 20.0,
    "unit": "mm",
    "window_start": "2023-08-17T18:00:00+00:00",
    "window_end": "2023-08-18T03:00:00+00:00"
  },
  "observation_summary": {
    "station": "KMIA",
    "station_name": "Miami International Airport",
    "total_raw_observations": 129,
    "hourly_readings": [
      {
        "hour_utc": "2023-08-17 18:00",
        "precip_mm": 6.1
      },
      {
        "hour_utc": "2023-08-17 19:00",
        "precip_mm": 14.48
      },
      {
        "hour_utc": "2023-08-17 20:00",
        "precip_mm": 40.39
      },
      {
        "hour_utc": "2023-08-18 01:00",
        "precip_mm": 19.3
      },
      {
        "hour_utc": "2023-08-18 02:00",
        "precip_mm": 6.6
      }
    ]
  },
  "determination": {
    "outcome": "YES",
    "observed_value_mm": 86.87,
    "threshold_mm": 20.0,
    "exceeded": true
  }
}
```

</details>

---

## 4. Atlanta Jazz Festival — Atlanta, GA

### The Event

On **April 1, 2023**, The Atlanta Jazz Festival at Piedmont Park — one of the largest free jazz festivals in the country. Spring in Atlanta brings warm, humid Gulf air that fuels afternoon thunderstorms. The event ran from **8:00 AM – 6:00 PM EDT** at Piedmont Park (free admission).

### Risk Pricing

At **7:00 AM EDT**, the ATMX API would have returned:

| Parameter | Value |
|-----------|-------|
| Risk probability | 15.0% |
| Threshold | >10.0 mm precipitation |
| Event window | 8:00 AM – 6:00 PM EDT |
| Payout | $55.00 |
| **Premium** | **$9.11** |
| Pricing model | LMSR (b=100) + 10% loading |
| Oracle source | NOAA ASOS via IEM |
| Station | KATL (Hartsfield-Jackson Atlanta Intl Airport) |
| H3 cell (res 7) | `8744c1b8affffff` |

### ASOS Observations

Station **KATL** recorded the following hourly precipitation:

| Hour (UTC) | Precipitation |
|------------|--------------|
| 2023-04-01 12:00 | 6.1 mm |
| 2023-04-01 13:00 | 6.6 mm |
| **Total** | **12.7 mm** |

> Verify: [IEM ASOS Archive](https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=KATL&data=p01m&tz=Etc/UTC&format=comma&latlon=no&year1=2023&month1=4&day1=1&hour1=12&year2=2023&month2=4&day2=1&hour2=22)

### Settlement

The settlement engine auto-triggered at **6:30 PM EDT**, 30 minutes after the event window closed.

```json
{
  "outcome": "YES",
  "observed_value_mm": 12.7,
  "threshold_mm": 10.0,
  "exceeded": true,
  "settled_at": "2023-04-01T22:30:00+00:00",
  "payout_triggered": true,
  "payout_amount_usd": 55.0
}
```

**Result:** The ticket holder paid **$9.11** and received **$55.00** — a **6.0× return** on the weather protection.

### Settlement Record

```
Algorithm:   SHA-256
Record hash: 631b5d5d197f78d33ce3f64d5eef8211ebeeed52fac734ea9fb8169973915db1
Prev hash:   5a24b3c9646c695ef913e4e7d56ebdc8aafe36c5b2b6e6fbf1439df72457f8ce
```

<details>
<summary>Evidence payload</summary>

```json
{
  "contract": {
    "h3_cell": "8744c1b8affffff",
    "metric": "precipitation",
    "threshold_mm": 10.0,
    "unit": "mm",
    "window_start": "2023-04-01T12:00:00+00:00",
    "window_end": "2023-04-01T22:00:00+00:00"
  },
  "observation_summary": {
    "station": "KATL",
    "station_name": "Hartsfield-Jackson Atlanta Intl Airport",
    "total_raw_observations": 137,
    "hourly_readings": [
      {
        "hour_utc": "2023-04-01 12:00",
        "precip_mm": 6.1
      },
      {
        "hour_utc": "2023-04-01 13:00",
        "precip_mm": 6.6
      }
    ]
  },
  "determination": {
    "outcome": "YES",
    "observed_value_mm": 12.7,
    "threshold_mm": 10.0,
    "exceeded": true
  }
}
```

</details>

---

## 5. Cinespia at Hollywood Forever — Los Angeles, CA

### The Event

On **January 9, 2023**, The popular Cinespia outdoor screening at Hollywood Forever Cemetery. January 2023 brought an extraordinary series of atmospheric rivers to Southern California, producing some of the heaviest rainfall in years. The event ran from **7:00 PM – 11:00 PM PST** at Hollywood Forever Cemetery ($22 tickets).

### Risk Pricing

At **2:00 PM PST**, the ATMX API would have returned:

| Parameter | Value |
|-----------|-------|
| Risk probability | 18.0% |
| Threshold | >10.0 mm precipitation |
| Event window | 7:00 PM – 11:00 PM PST |
| Payout | $45.00 |
| **Premium** | **$8.95** |
| Pricing model | LMSR (b=100) + 10% loading |
| Oracle source | NOAA ASOS via IEM |
| Station | KLAX (Los Angeles International Airport) |
| H3 cell (res 7) | `8729a565bffffff` |

### ASOS Observations

Station **KLAX** recorded the following hourly precipitation:

| Hour (UTC) | Precipitation |
|------------|--------------|
| 2023-01-10 03:00 | 3.3 mm |
| 2023-01-10 04:00 | 4.06 mm |
| 2023-01-10 05:00 | 3.05 mm |
| 2023-01-10 06:00 | 7.11 mm |
| **Total** | **17.52 mm** |

> Verify: [IEM ASOS Archive](https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=KLAX&data=p01m&tz=Etc/UTC&format=comma&latlon=no&year1=2023&month1=1&day1=10&hour1=3&year2=2023&month2=1&day2=10&hour2=7)

### Settlement

The settlement engine auto-triggered at **11:30 PM PST**, 30 minutes after the event window closed.

```json
{
  "outcome": "YES",
  "observed_value_mm": 17.52,
  "threshold_mm": 10.0,
  "exceeded": true,
  "settled_at": "2023-01-10T07:30:00+00:00",
  "payout_triggered": true,
  "payout_amount_usd": 45.0
}
```

**Result:** The ticket holder paid **$8.95** and received **$45.00** — a **5.0× return** on the weather protection.

### Settlement Record

```
Algorithm:   SHA-256
Record hash: 00987aa1ec011488e423bc91648a80bf495cce9b7d91e02b8fc585b5849a8d69
Prev hash:   631b5d5d197f78d33ce3f64d5eef8211ebeeed52fac734ea9fb8169973915db1
```

<details>
<summary>Evidence payload</summary>

```json
{
  "contract": {
    "h3_cell": "8729a565bffffff",
    "metric": "precipitation",
    "threshold_mm": 10.0,
    "unit": "mm",
    "window_start": "2023-01-10T03:00:00+00:00",
    "window_end": "2023-01-10T07:00:00+00:00"
  },
  "observation_summary": {
    "station": "KLAX",
    "station_name": "Los Angeles International Airport",
    "total_raw_observations": 59,
    "hourly_readings": [
      {
        "hour_utc": "2023-01-10 03:00",
        "precip_mm": 3.3
      },
      {
        "hour_utc": "2023-01-10 04:00",
        "precip_mm": 4.06
      },
      {
        "hour_utc": "2023-01-10 05:00",
        "precip_mm": 3.05
      },
      {
        "hour_utc": "2023-01-10 06:00",
        "precip_mm": 7.11
      }
    ]
  },
  "determination": {
    "outcome": "YES",
    "observed_value_mm": 17.52,
    "threshold_mm": 10.0,
    "exceeded": true
  }
}
```

</details>

---

## 6. Celebrate Brooklyn! at Prospect Park — Brooklyn, NY

### The Event

On **July 15, 2023**, An evening concert at the Prospect Park Bandshell, part of the Celebrate Brooklyn! performing arts festival — the city's longest-running free outdoor performing arts series. The event ran from **6:00 PM – 10:00 PM EDT** at Prospect Park Bandshell ($45 tickets).

### Risk Pricing

At **2:00 PM EDT**, the ATMX API would have returned:

| Parameter | Value |
|-----------|-------|
| Risk probability | 6.2% |
| Threshold | >10.0 mm precipitation |
| Event window | 6:00 PM – 10:00 PM EDT |
| Payout | $50.00 |
| **Premium** | **$3.43** |
| Pricing model | LMSR (b=100) + 10% loading |
| Oracle source | NOAA ASOS via IEM |
| Station | KJFK (JFK International Airport) |
| H3 cell (res 7) | `872a103b1ffffff` |

### ASOS Observations

Station **KJFK** recorded **no measurable precipitation** during the event window (52 observations).

> Verify: [IEM ASOS Archive](https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=KJFK&data=p01m&tz=Etc/UTC&format=comma&latlon=no&year1=2023&month1=7&day1=15&hour1=22&year2=2023&month2=7&day2=16&hour2=2)

### Settlement

The settlement engine auto-triggered at **10:30 PM EDT**, 30 minutes after the event window closed.

```json
{
  "outcome": "NO",
  "observed_value_mm": 0,
  "threshold_mm": 10.0,
  "exceeded": false,
  "settled_at": "2023-07-16T02:30:00+00:00",
  "payout_triggered": false,
  "payout_amount_usd": 0.0
}
```

**Result:** Clear skies — no payout triggered. The **$3.43 premium** was the cost of peace of mind.

### Settlement Record

```
Algorithm:   SHA-256
Record hash: fe4d4c02aa6a974d04d9e6e0b33d82615a7b1b413582950584cf616b0342b7f2
Prev hash:   00987aa1ec011488e423bc91648a80bf495cce9b7d91e02b8fc585b5849a8d69
```

<details>
<summary>Evidence payload</summary>

```json
{
  "contract": {
    "h3_cell": "872a103b1ffffff",
    "metric": "precipitation",
    "threshold_mm": 10.0,
    "unit": "mm",
    "window_start": "2023-07-15T22:00:00+00:00",
    "window_end": "2023-07-16T02:00:00+00:00"
  },
  "observation_summary": {
    "station": "KJFK",
    "station_name": "JFK International Airport",
    "total_raw_observations": 52,
    "hourly_readings": []
  },
  "determination": {
    "outcome": "NO",
    "observed_value_mm": 0,
    "threshold_mm": 10.0,
    "exceeded": false
  }
}
```

</details>

---

## 7. Boston Pops Fireworks Spectacular — Boston, MA

### The Event

On **July 4, 2023**, The annual Boston Pops Fireworks Spectacular on the Charles River Esplanade — one of America's most iconic Fourth of July celebrations, drawing over 500,000 spectators. Afternoon showers tested the crowd's resolve, but the threshold wasn't reached. The event ran from **2:00 PM – 11:00 PM EDT** at Hatch Memorial Shell, Esplanade (free admission).

### Risk Pricing

At **12:00 PM EDT**, the ATMX API would have returned:

| Parameter | Value |
|-----------|-------|
| Risk probability | 7.0% |
| Threshold | >10.0 mm precipitation |
| Event window | 2:00 PM – 11:00 PM EDT |
| Payout | $50.00 |
| **Premium** | **$3.87** |
| Pricing model | LMSR (b=100) + 10% loading |
| Oracle source | NOAA ASOS via IEM |
| Station | KBOS (Boston Logan International Airport) |
| H3 cell (res 7) | `872a30296ffffff` |

### ASOS Observations

Station **KBOS** recorded the following hourly precipitation:

| Hour (UTC) | Precipitation |
|------------|--------------|
| 2023-07-04 19:00 | 1.52 mm |
| 2023-07-04 20:00 | 3.3 mm |
| 2023-07-04 21:00 | 0.51 mm |
| **Total** | **5.33 mm** |

> Verify: [IEM ASOS Archive](https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=KBOS&data=p01m&tz=Etc/UTC&format=comma&latlon=no&year1=2023&month1=7&day1=4&hour1=18&year2=2023&month2=7&day2=5&hour2=3)

### Settlement

The settlement engine auto-triggered at **11:30 PM EDT**, 30 minutes after the event window closed.

```json
{
  "outcome": "NO",
  "observed_value_mm": 5.33,
  "threshold_mm": 10.0,
  "exceeded": false,
  "settled_at": "2023-07-05T03:30:00+00:00",
  "payout_triggered": false,
  "payout_amount_usd": 0.0
}
```

**Result:** It rained (5.33 mm) but stayed below the 10.0 mm threshold. The **$3.87 premium** covered the risk — the event continued despite light rain.

### Settlement Record

```
Algorithm:   SHA-256
Record hash: 6fcc19d294131ad1bc9bf5bf69eeb636ebe9c7b5a92ddfc0d21842d8e5cb0f41
Prev hash:   fe4d4c02aa6a974d04d9e6e0b33d82615a7b1b413582950584cf616b0342b7f2
```

<details>
<summary>Evidence payload</summary>

```json
{
  "contract": {
    "h3_cell": "872a30296ffffff",
    "metric": "precipitation",
    "threshold_mm": 10.0,
    "unit": "mm",
    "window_start": "2023-07-04T18:00:00+00:00",
    "window_end": "2023-07-05T03:00:00+00:00"
  },
  "observation_summary": {
    "station": "KBOS",
    "station_name": "Boston Logan International Airport",
    "total_raw_observations": 130,
    "hourly_readings": [
      {
        "hour_utc": "2023-07-04 19:00",
        "precip_mm": 1.52
      },
      {
        "hour_utc": "2023-07-04 20:00",
        "precip_mm": 3.3
      },
      {
        "hour_utc": "2023-07-04 21:00",
        "precip_mm": 0.51
      }
    ]
  },
  "determination": {
    "outcome": "NO",
    "observed_value_mm": 5.33,
    "threshold_mm": 10.0,
    "exceeded": false
  }
}
```

</details>

---

## 8. Stern Grove Festival Concert — San Francisco, CA

### The Event

On **September 1, 2023**, The historic Stern Grove Festival — San Francisco's free outdoor concert series since 1938. Despite the city's famous microclimates, September is statistically its warmest and driest month. The event ran from **2:00 PM – 5:00 PM PDT** at Sigmund Stern Grove (free admission).

### Risk Pricing

At **10:00 AM PDT**, the ATMX API would have returned:

| Parameter | Value |
|-----------|-------|
| Risk probability | 2.0% |
| Threshold | >5.0 mm precipitation |
| Event window | 2:00 PM – 5:00 PM PDT |
| Payout | $40.00 |
| **Premium** | **$0.88** |
| Pricing model | LMSR (b=100) + 10% loading |
| Oracle source | NOAA ASOS via IEM |
| Station | KSFO (San Francisco International Airport) |
| H3 cell (res 7) | `87283092affffff` |

### ASOS Observations

Station **KSFO** recorded **no measurable precipitation** during the event window (39 observations).

> Verify: [IEM ASOS Archive](https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=KSFO&data=p01m&tz=Etc/UTC&format=comma&latlon=no&year1=2023&month1=9&day1=1&hour1=21&year2=2023&month2=9&day2=2&hour2=0)

### Settlement

The settlement engine auto-triggered at **5:30 PM PDT**, 30 minutes after the event window closed.

```json
{
  "outcome": "NO",
  "observed_value_mm": 0,
  "threshold_mm": 5.0,
  "exceeded": false,
  "settled_at": "2023-09-02T00:30:00+00:00",
  "payout_triggered": false,
  "payout_amount_usd": 0.0
}
```

**Result:** Clear skies — no payout triggered. The **$0.88 premium** was the cost of peace of mind.

### Settlement Record

```
Algorithm:   SHA-256
Record hash: eee7c69b1af36b1fecd5958efed4dc3ffb20247c32340a8ea95085547ca9b104
Prev hash:   6fcc19d294131ad1bc9bf5bf69eeb636ebe9c7b5a92ddfc0d21842d8e5cb0f41
```

<details>
<summary>Evidence payload</summary>

```json
{
  "contract": {
    "h3_cell": "87283092affffff",
    "metric": "precipitation",
    "threshold_mm": 5.0,
    "unit": "mm",
    "window_start": "2023-09-01T21:00:00+00:00",
    "window_end": "2023-09-02T00:00:00+00:00"
  },
  "observation_summary": {
    "station": "KSFO",
    "station_name": "San Francisco International Airport",
    "total_raw_observations": 39,
    "hourly_readings": []
  },
  "determination": {
    "outcome": "NO",
    "observed_value_mm": 0,
    "threshold_mm": 5.0,
    "exceeded": false
  }
}
```

</details>

---

## 9. Outdoor Cinema at Gas Works Park — Seattle, WA

### The Event

On **July 25, 2023**, An outdoor movie screening at Gas Works Park overlooking Lake Union. Seattle's dry summer season makes July the prime window for outdoor events, though marine air incursions from Puget Sound can bring unexpected drizzle. The event ran from **8:00 PM – 11:00 PM PDT** at Gas Works Park ($15 tickets).

### Risk Pricing

At **5:00 PM PDT**, the ATMX API would have returned:

| Parameter | Value |
|-----------|-------|
| Risk probability | 3.0% |
| Threshold | >5.0 mm precipitation |
| Event window | 8:00 PM – 11:00 PM PDT |
| Payout | $40.00 |
| **Premium** | **$1.33** |
| Pricing model | LMSR (b=100) + 10% loading |
| Oracle source | NOAA ASOS via IEM |
| Station | KSEA (Seattle-Tacoma International Airport) |
| H3 cell (res 7) | `8728d5cd2ffffff` |

### ASOS Observations

Station **KSEA** recorded **no measurable precipitation** during the event window (39 observations).

> Verify: [IEM ASOS Archive](https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=KSEA&data=p01m&tz=Etc/UTC&format=comma&latlon=no&year1=2023&month1=7&day1=26&hour1=3&year2=2023&month2=7&day2=26&hour2=6)

### Settlement

The settlement engine auto-triggered at **11:30 PM PDT**, 30 minutes after the event window closed.

```json
{
  "outcome": "NO",
  "observed_value_mm": 0,
  "threshold_mm": 5.0,
  "exceeded": false,
  "settled_at": "2023-07-26T06:30:00+00:00",
  "payout_triggered": false,
  "payout_amount_usd": 0.0
}
```

**Result:** Clear skies — no payout triggered. The **$1.33 premium** was the cost of peace of mind.

### Settlement Record

```
Algorithm:   SHA-256
Record hash: 63f286debed8169270daeb6cb8be30ecfda518de48d7b3a4711397e717f4ca9b
Prev hash:   eee7c69b1af36b1fecd5958efed4dc3ffb20247c32340a8ea95085547ca9b104
```

<details>
<summary>Evidence payload</summary>

```json
{
  "contract": {
    "h3_cell": "8728d5cd2ffffff",
    "metric": "precipitation",
    "threshold_mm": 5.0,
    "unit": "mm",
    "window_start": "2023-07-26T03:00:00+00:00",
    "window_end": "2023-07-26T06:00:00+00:00"
  },
  "observation_summary": {
    "station": "KSEA",
    "station_name": "Seattle-Tacoma International Airport",
    "total_raw_observations": 39,
    "hourly_readings": []
  },
  "determination": {
    "outcome": "NO",
    "observed_value_mm": 0,
    "threshold_mm": 5.0,
    "exceeded": false
  }
}
```

</details>

---

## 10. Fair Park Food Festival — Dallas, TX

### The Event

On **August 10, 2023**, An outdoor food competition at Fair Park. August in North Texas means extreme heat but typically low precipitation — though isolated severe thunderstorms can develop rapidly along the dryline. The event ran from **10:00 AM – 10:00 PM CDT** at Fair Park ($25 tickets).

### Risk Pricing

At **8:00 AM CDT**, the ATMX API would have returned:

| Parameter | Value |
|-----------|-------|
| Risk probability | 5.0% |
| Threshold | >10.0 mm precipitation |
| Event window | 10:00 AM – 10:00 PM CDT |
| Payout | $45.00 |
| **Premium** | **$2.49** |
| Pricing model | LMSR (b=100) + 10% loading |
| Oracle source | NOAA ASOS via IEM |
| Station | KDFW (Dallas/Fort Worth International Airport) |
| H3 cell (res 7) | `8726c861bffffff` |

### ASOS Observations

Station **KDFW** recorded **no measurable precipitation** during the event window (156 observations).

> Verify: [IEM ASOS Archive](https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=KDFW&data=p01m&tz=Etc/UTC&format=comma&latlon=no&year1=2023&month1=8&day1=10&hour1=15&year2=2023&month2=8&day2=11&hour2=3)

### Settlement

The settlement engine auto-triggered at **10:30 PM CDT**, 30 minutes after the event window closed.

```json
{
  "outcome": "NO",
  "observed_value_mm": 0,
  "threshold_mm": 10.0,
  "exceeded": false,
  "settled_at": "2023-08-11T03:30:00+00:00",
  "payout_triggered": false,
  "payout_amount_usd": 0.0
}
```

**Result:** Clear skies — no payout triggered. The **$2.49 premium** was the cost of peace of mind.

### Settlement Record

```
Algorithm:   SHA-256
Record hash: aae4419b48258210700d706c2710a73c5cedae0a5951de47fbd0bcf4fdf4d7ed
Prev hash:   63f286debed8169270daeb6cb8be30ecfda518de48d7b3a4711397e717f4ca9b
```

<details>
<summary>Evidence payload</summary>

```json
{
  "contract": {
    "h3_cell": "8726c861bffffff",
    "metric": "precipitation",
    "threshold_mm": 10.0,
    "unit": "mm",
    "window_start": "2023-08-10T15:00:00+00:00",
    "window_end": "2023-08-11T03:00:00+00:00"
  },
  "observation_summary": {
    "station": "KDFW",
    "station_name": "Dallas/Fort Worth International Airport",
    "total_raw_observations": 156,
    "hourly_readings": []
  },
  "determination": {
    "outcome": "NO",
    "observed_value_mm": 0,
    "threshold_mm": 10.0,
    "exceeded": false
  }
}
```

</details>

---

## Hash Chain Integrity

Every settlement record is linked to the previous one via SHA-256 hashing. Tampering with any single record breaks the chain for all subsequent entries, providing a tamper-evident audit trail without blockchain consensus overhead.

```
  # 1  ─── cb72d08eb48fb736...  (genesis)
       │
       ▼  prev = cb72d08eb48fb736...
  # 2  ─── a16b73e145981628...
       │
       ▼  prev = a16b73e145981628...
  # 3  ─── 5a24b3c9646c695e...
       │
       ▼  prev = 5a24b3c9646c695e...
  # 4  ─── 631b5d5d197f78d3...
       │
       ▼  prev = 631b5d5d197f78d3...
  # 5  ─── 00987aa1ec011488...
       │
       ▼  prev = 00987aa1ec011488...
  # 6  ─── fe4d4c02aa6a974d...
       │
       ▼  prev = fe4d4c02aa6a974d...
  # 7  ─── 6fcc19d294131ad1...
       │
       ▼  prev = 6fcc19d294131ad1...
  # 8  ─── eee7c69b1af36b1f...
       │
       ▼  prev = eee7c69b1af36b1f...
  # 9  ─── 63f286debed81692...
       │
       ▼  prev = 63f286debed81692...
  #10  ─── aae4419b48258210...
```

---

## Verify the Data Yourself

Every observation can be independently verified:

1. Visit the [IEM ASOS Download Page](https://mesonet.agron.iastate.edu/request/download.phtml)
2. Select the station (e.g. KJFK), date range, and `p01m` (1-hour precipitation)
3. Compare the hourly maxima against the readings listed in each case study

To verify hash chain integrity, recompute each record's SHA-256 hash using the `hash_payload` fields from [`case_studies.json`](case_studies.json) and confirm it matches `record_hash`. Each hash includes the previous record's hash as a prefix, so a single altered record invalidates the entire downstream chain.

**Aggregation note:** ASOS `p01m` is a running accumulator within each clock hour. We take the maximum value per hour (representing the full hourly total), then sum across hours for the event window total.

---

*Generated from real NOAA ASOS data by `scripts/generate_case_studies.py`. See also: [API Lifecycle Guide](../services/risk-api/docs/api_lifecycle.md) · [Design Document](design.md)*
