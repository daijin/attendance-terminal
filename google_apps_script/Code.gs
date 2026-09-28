/**
 * Bind this script to the destination spreadsheet.
 * Set Script Property UPLOAD_SECRET before deployment.
 */
function doGet() {
  return jsonResponse_({ok: true, service: 'attendance-upload'});
}

function doPost(e) {
  const lock = LockService.getScriptLock();
  try {
    const payload = JSON.parse(e.postData.contents);
    const expected = PropertiesService.getScriptProperties().getProperty('UPLOAD_SECRET');
    if (!expected || payload.secret !== expected) {
      return jsonResponse_({ok: false, error: 'unauthorized'});
    }
    if (!Array.isArray(payload.events) || payload.events.length > 500) {
      return jsonResponse_({ok: false, error: 'invalid events'});
    }

    lock.waitLock(30000);
    const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
    const sheetName = String(payload.sheet_name || '打刻ログ');
    let sheet = spreadsheet.getSheetByName(sheetName);
    if (!sheet) {
      sheet = spreadsheet.insertSheet(sheetName);
    }
    ensureHeader_(sheet);

    // Deduplicate by globally unique event_id. UUID + device_id makes retries and
    // uploads from multiple terminals safe even after an ambiguous HTTP failure.
    const lastRow = sheet.getLastRow();
    const knownIds = new Set(
      lastRow < 2
        ? []
        : sheet.getRange(2, 1, lastRow - 1, 1).getDisplayValues().flat()
    );
    const acknowledged = [];
    const rows = [];
    payload.events.forEach(function(event) {
      validateEvent_(event);
      acknowledged.push(event.event_id);
      if (!knownIds.has(event.event_id)) {
        rows.push([
          event.event_id,
          event.device_id,
          event.uid,
          event.punched_at,
          event.created_at,
          new Date()
        ]);
        knownIds.add(event.event_id);
      }
    });
    if (rows.length) {
      sheet.getRange(sheet.getLastRow() + 1, 1, rows.length, rows[0].length).setValues(rows);
    }
    return jsonResponse_({ok: true, acknowledged_event_ids: acknowledged, inserted: rows.length});
  } catch (error) {
    console.error(error);
    return jsonResponse_({ok: false, error: String(error.message || error)});
  } finally {
    try { lock.releaseLock(); } catch (_) {}
  }
}

function ensureHeader_(sheet) {
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(['event_id', 'device_id', 'uid', 'punched_at', 'created_at', 'uploaded_at']);
    sheet.setFrozenRows(1);
  }
}

function validateEvent_(event) {
  ['event_id', 'device_id', 'uid', 'punched_at', 'created_at'].forEach(function(key) {
    if (typeof event[key] !== 'string' || !event[key] || event[key].length > 128) {
      throw new Error('invalid event field: ' + key);
    }
  });
}

function jsonResponse_(value) {
  return ContentService.createTextOutput(JSON.stringify(value))
    .setMimeType(ContentService.MimeType.JSON);
}
