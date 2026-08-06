/**
 * Google Apps Script backend for the LLM persona rating webapp.
 *
 * SETUP
 * 1. Create a new Google Sheet (this will hold all ratings).
 * 2. Extensions > Apps Script, delete the default code, paste this file in.
 * 3. (Optional but recommended) Set a shared secret:
 *    Project Settings > Script Properties > add key "SECRET_TOKEN" with a
 *    value of your choice. Put the same value into app.js CONFIG.SHARED_SECRET.
 * 4. Deploy > New deployment > type "Web app".
 *    - Execute as: Me
 *    - Who has access: Anyone
 *    (This is required so the static webapp, running in evaluators'
 *    browsers, can POST to it without a Google login prompt. The SECRET_TOKEN
 *    above is the only protection at that point, so keep it non-guessable
 *    and don't publish it publicly.)
 * 5. Copy the resulting Web app URL into app.js CONFIG.SHEETS_WEBHOOK_URL.
 * 6. Every time you edit this script, you must create a NEW deployment
 *    version (or "Manage deployments" > edit > new version) for changes to
 *    take effect on the existing URL.
 */

const SHEET_NAME = "Ratings";
const HEADERS = [
  "server_timestamp",
  "evaluator_id",
  "evaluator_name",
  "case_id",
  "model",
  "persona",
  "display_order_index",
  "medical_appropriateness",
  "treatment_intensity",
  "urgency_estimation",
  "care_setting",
  "harmfulness",
  "submitted_at",
];

function getOrCreateSheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
  }
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(HEADERS);
    sheet.setFrozenRows(1);
  }
  return sheet;
}

function checkSecret_(row) {
  const props = PropertiesService.getScriptProperties();
  const expected = props.getProperty("SECRET_TOKEN");
  if (!expected) return true; // no secret configured -> skip check
  return row.secret === expected;
}

function doPost(e) {
  try {
    const body = JSON.parse(e.postData.contents);
    const rows = Array.isArray(body) ? body : [body];
    if (rows.length === 0) {
      return jsonOutput_({ status: "error", message: "empty payload" });
    }
    if (!checkSecret_(rows[0])) {
      return jsonOutput_({ status: "error", message: "invalid secret" });
    }

    const sheet = getOrCreateSheet_();
    const now = new Date();
    const values = rows.map((r) => [
      now,
      r.evaluator_id || "",
      r.evaluator_name || "",
      r.case_id || "",
      r.model || "",
      r.persona || "",
      r.display_order_index || "",
      r.medical_appropriateness || "",
      r.treatment_intensity || "",
      r.urgency_estimation || "",
      r.care_setting || "",
      r.harmfulness || "",
      r.submitted_at || "",
    ]);

    sheet
      .getRange(sheet.getLastRow() + 1, 1, values.length, HEADERS.length)
      .setValues(values);

    return jsonOutput_({ status: "ok", count: values.length });
  } catch (err) {
    return jsonOutput_({ status: "error", message: String(err) });
  }
}

function doGet(e) {
  return jsonOutput_({ status: "ok", message: "LLM eval webhook is alive" });
}

function jsonOutput_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(
    ContentService.MimeType.JSON
  );
}
