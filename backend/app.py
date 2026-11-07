
import ephem

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware


# ==========================================================
# TOBAGO SETTINGS
# ==========================================================

TOBAGO_TZ = ZoneInfo("America/Port_of_Spain")

WINDOW_DAYS = 2

PHASE_FUNCTIONS = {
    "New Moon": ephem.next_new_moon,
    "First Quarter": ephem.next_first_quarter_moon,
    "Full Moon": ephem.next_full_moon,
    "Last Quarter": ephem.next_last_quarter_moon,
}

STAGES = [
    "New Moon",
    "Waxing Crescent",
    "First Quarter",
    "Waxing Gibbous",
    "Full Moon",
    "Waning Gibbous",
    "Last Quarter",
    "Waning Crescent",
]


# ==========================================================
# FASTAPI APPLICATION
# ==========================================================

app = FastAPI(
    title="Tobago Moon & Tide API",
    description="PyEphem-powered lunar and tide classification service",
    version="1.0.0",
)


# Netlify will proxy API requests to this service.
# Direct API access is also available if needed.

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ==========================================================
# DATE AND TIME HELPERS
# ==========================================================

def utc_datetime_to_tobago(value):
    return value.astimezone(TOBAGO_TZ)


def ephem_to_utc(value):
    return value.datetime().replace(tzinfo=timezone.utc)


def month_start_utc(year, month):
    return datetime(
        year,
        month,
        1,
        tzinfo=timezone.utc
    )


def next_month_start(year, month):

    if month == 12:
        return datetime(
            year + 1,
            1,
            1,
            tzinfo=timezone.utc
        )

    return datetime(
        year,
        month + 1,
        1,
        tzinfo=timezone.utc
    )


# ==========================================================
# CURRENT MOON CALCULATIONS
# ==========================================================

def get_current_moon():

    now = datetime.now(timezone.utc)

    observer = ephem.Observer()

    observer.date = ephem.Date(now.replace(tzinfo=None))

    moon = ephem.Moon(observer)

    illumination = float(moon.phase)

    previous_new = ephem.previous_new_moon(observer.date)

    age = float(
        observer.date - previous_new
    )

    next_new = ephem.next_new_moon(observer.date)

    cycle_length = float(
        next_new - previous_new
    )

    fraction = age / cycle_length

    index = int(
        (fraction * 8 + 0.5) % 8
    )

    return {
        "phase": STAGES[index],
        "illumination": round(illumination, 2),
        "age": round(age, 2),
        "fraction": round(fraction, 6),
        "timestamp": int(now.timestamp() * 1000),
        "timezone": "America/Port_of_Spain",
    }


# ==========================================================
# MONTHLY LUNAR PHASE EVENTS
# ==========================================================

def get_monthly_phases(year, month):

    start = month_start_utc(year, month)

    end = next_month_start(year, month)

    events = []

    for phase_name, phase_function in PHASE_FUNCTIONS.items():

        current = ephem.Date(
            start.replace(tzinfo=None)
        )

        while True:

            phase_date = phase_function(current)

            utc_event = ephem_to_utc(phase_date)

            if utc_event >= end:
                break

            if utc_event >= start:

                local_event = utc_datetime_to_tobago(
                    utc_event
                )

                events.append({
                    "phase": phase_name,
                    "timestamp": int(
                        utc_event.timestamp() * 1000
                    ),
                    "local_date": local_event.strftime(
                        "%Y-%m-%d"
                    ),
                    "local_time": local_event.strftime(
                        "%H:%M"
                    ),
                    "timezone": "AST",
                })

            current = phase_date + ephem.second

    events.sort(
        key=lambda event: event["timestamp"]
    )

    return events


# ==========================================================
# DAILY TIDE CLASSIFICATION
# ==========================================================

def get_tide_days(year, month):

    start = date(year, month, 1)

    if month == 12:

        next_month = date(year + 1, 1, 1)

    else:

        next_month = date(year, month + 1, 1)

    end = next_month - timedelta(days=1)

    search_start = start - timedelta(days=WINDOW_DAYS)

    search_end = end + timedelta(days=WINDOW_DAYS)

    events_by_date = {}

    # Find astronomical phase events.

    for phase_name, phase_function in PHASE_FUNCTIONS.items():

        current = ephem.Date(
            datetime(
                search_start.year,
                search_start.month,
                search_start.day,
                tzinfo=timezone.utc,
            ).replace(tzinfo=None)
        )

        while True:

            phase_date = phase_function(current)

            utc_datetime = ephem_to_utc(phase_date)

            local_datetime = utc_datetime_to_tobago(
                utc_datetime
            )

            event_date = local_datetime.date()

            if event_date > search_end:
                break

            if event_date >= search_start:

                events_by_date.setdefault(
                    event_date,
                    []
                ).append(phase_name)

            current = phase_date + ephem.second

    # Calculate spring and neap windows.

    spring_dates = set()

    neap_dates = set()

    for event_date, phases in events_by_date.items():

        for phase in phases:

            target = (
                spring_dates
                if phase in ("New Moon", "Full Moon")
                else neap_dates
            )

            for offset in range(
                -WINDOW_DAYS,
                WINDOW_DAYS + 1
            ):

                target.add(
                    event_date + timedelta(days=offset)
                )

    # Generate daily results.

    results = []

    current_date = start

    while current_date <= end:

        phases = events_by_date.get(
            current_date,
            []
        )

        if current_date in spring_dates:

            classification = "Spring"

        elif current_date in neap_dates:

            classification = "Neap"

        else:

            classification = "Neither"

        results.append({

            "date": f"{current_date.strftime('%a, %b')} {current_date.day}",

            "classification": classification,

            "phases": ", ".join(phases),

        })

        current_date += timedelta(days=1)

    return results


# ==========================================================
# API ENDPOINTS
# ==========================================================

@app.get("/")
def home():

    return {
        "message": "Tobago Moon & Tide API is running",
        "astronomy_engine": "PyEphem",
        "timezone": "America/Port_of_Spain",
        "version": "1.0.0",
    }


@app.get("/api/moon")
def moon():

    try:

        return get_current_moon()

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail="Unable to calculate current moon phase."
        ) from error


@app.get("/api/phases")
def phases(

    year: int = Query(ge=1900, le=2200),

    month: int = Query(ge=1, le=12),

):

    try:

        return get_monthly_phases(
            year,
            month
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail="Unable to calculate monthly lunar phases."
        ) from error


@app.get("/api/tides")
def tides(

    year: int = Query(ge=1900, le=2200),

    month: int = Query(ge=1, le=12),

):

    try:

        return get_tide_days(
            year,
            month
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail="Unable to calculate tide classifications."
        ) from error
