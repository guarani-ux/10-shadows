//! time_utils.rs — Pure-Rust Standard Library RFC3339 Timestamp Formatting.

use std::time::{SystemTime, UNIX_EPOCH};

pub fn current_timestamp_rfc3339() -> String {
    let duration = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default();
    let total_secs = duration.as_secs();
    let millis = duration.subsec_millis();

    // Standard Gregorian calendar calculation from Unix Epoch (1970-01-01)
    let sec_in_day = total_secs % 86400;
    let hours = sec_in_day / 3600;
    let mins = (sec_in_day % 3600) / 60;
    let secs = sec_in_day % 60;

    let mut days = (total_secs / 86400) as i64;
    let mut year = 1970;

    loop {
        let leap = if (year % 4 == 0 && year % 100 != 0) || (year % 400 == 0) {
            1
        } else {
            0
        };
        let days_in_year = 365 + leap;
        if days >= days_in_year {
            days -= days_in_year;
            year += 1;
        } else {
            break;
        }
    }

    let leap = if (year % 4 == 0 && year % 100 != 0) || (year % 400 == 0) {
        1
    } else {
        0
    };
    let month_days = [31, 28 + leap, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    let mut month = 1;
    for &md in &month_days {
        if days >= md as i64 {
            days -= md as i64;
            month += 1;
        } else {
            break;
        }
    }
    let day = days + 1;

    format!(
        "{:04}-{:02}-{:02}T{:02}:{:02}:{:02}.{:03}Z",
        year, month, day, hours, mins, secs, millis
    )
}
