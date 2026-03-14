#!/usr/bin/env python3
"""
scripts/apply_corrections.py
-----------------------------
Apply calibration corrections (dx_mm / dy_mm) to the mapping JSON.

The mapping JSON stores field positions in canvas pixels (800x1131).
The calibration tool uses MM = 0.26274 canvas_px/mm for conversion.

Formula:  new_x = old_x + dx_mm / MM
          new_y = old_y + dy_mm / MM

Usage:
    python scripts/apply_corrections.py [--dry-run]
"""
import json, shutil, sys
from pathlib import Path
from datetime import date

MM = 0.26274   # canvas_px per mm  (matches calibrate_html.py)

BASE    = Path(__file__).parent.parent
MAPPING = BASE / "NEW 3" / "form_101_mapping_1772880459281.json"

CORRECTIONS = {
  "meta.tax_year": {"dx_mm": 22.65, "dy_mm": 7.71},
  "employer.name": {"dx_mm": 43.21, "dy_mm": 14.25},
  "employee.email": {"dx_mm": 48.11, "dy_mm": 29.19},
  "employee.phone": {"dx_mm": 20.32, "dy_mm": 28.26},
  "employee.id": {"dx_mm": 43.21, "dy_mm": 20.79},
  "employee.last_name": {"dx_mm": 33.86, "dy_mm": 21.02},
  "employee.gender.male": {"dx_mm": 48.11, "dy_mm": 25.46},
  "spouse.passport": {"dx_mm": 45.07, "dy_mm": 65.39},
  "spouse.id": {"dx_mm": 44.37, "dy_mm": 62.82},
  "spouse.last_name": {"dx_mm": 31.76, "dy_mm": 62.12},
  "spouse.first_name": {"dx_mm": 24.29, "dy_mm": 62.59},
  "spouse.birth_date": {"dx_mm": 12.61, "dy_mm": 62.82},
  "spouse.immigration_date": {"dx_mm": 4.67, "dy_mm": 62.36},
  "spouse.has_income.none": {"dx_mm": 37.37, "dy_mm": 65.63},
  "spouse.has_income.yes": {"dx_mm": 25.46, "dy_mm": 64.46},
  "spouse.income_type.work": {"dx_mm": 14.71, "dy_mm": 65.39},
  "spouse.income_type.other": {"dx_mm": 8.64, "dy_mm": 64.93},
  "income.other.monthly_salary": {"dx_mm": 22.19, "dy_mm": 45.07},
  "income.other.additional_job": {"dx_mm": 21.72, "dy_mm": 46.01},
  "income.other.partial_salary": {"dx_mm": 21.95, "dy_mm": 47.18},
  "income.credit_request.get_credits_here": {"dx_mm": 21.49, "dy_mm": 56.99},
  "income.other.scholarship": {"dx_mm": 11.44, "dy_mm": 46.71},
  "income.other.pension": {"dx_mm": 11.21, "dy_mm": 45.78},
  "income.other.daily_worker": {"dx_mm": 10.98, "dy_mm": 45.07},
  "income.other.none": {"dx_mm": 22.42, "dy_mm": 41.1},
  "income.main.scholarship": {"dx_mm": 21.95, "dy_mm": 38.54},
  "children[0].in_custody": {"dx_mm": 48.34, "dy_mm": 34.56},
  "children[0].receives_allowance": {"dx_mm": 47.64, "dy_mm": 34.56},
  "children[0].name": {"dx_mm": 44.14, "dy_mm": 35.27},
  "children[0].id": {"dx_mm": 35.27, "dy_mm": 35.27},
  "children[0].birth_date": {"dx_mm": 25.69, "dy_mm": 35.27},
  "children[1].in_custody": {"dx_mm": 48.81, "dy_mm": 36.9},
  "children[1].receives_allowance": {"dx_mm": 46.94, "dy_mm": 36.9},
  "children[1].name": {"dx_mm": 43.67, "dy_mm": 36.9},
  "children[1].id": {"dx_mm": 35.5, "dy_mm": 36.9},
  "children[1].birth_date": {"dx_mm": 25.92, "dy_mm": 36.67},
  "children[2].in_custody": {"dx_mm": 48.34, "dy_mm": 39.24},
  "children[2].receives_allowance": {"dx_mm": 47.64, "dy_mm": 39.47},
  "children[2].name": {"dx_mm": 43.91, "dy_mm": 38.77},
  "children[2].id": {"dx_mm": 35.5, "dy_mm": 39.47},
  "children[2].birth_date": {"dx_mm": 26.62, "dy_mm": 39.0},
  "children[3].in_custody": {"dx_mm": 48.11, "dy_mm": 41.1},
  "children[3].receives_allowance": {"dx_mm": 47.64, "dy_mm": 41.57},
  "children[3].name": {"dx_mm": 44.14, "dy_mm": 41.1},
  "children[3].id": {"dx_mm": 35.5, "dy_mm": 42.27},
  "children[3].birth_date": {"dx_mm": 28.03, "dy_mm": 42.27},
  "income.main.pension": {"dx_mm": 21.95, "dy_mm": 36.9},
  "income.main.daily_worker": {"dx_mm": 21.95, "dy_mm": 36.43},
  "income.main.partial_salary": {"dx_mm": 22.42, "dy_mm": 35.03},
  "income.main.additional_job": {"dx_mm": 21.95, "dy_mm": 33.63},
  "employee.gender.female": {"dx_mm": 48.34, "dy_mm": 27.32},
  "employee.marital_status.single": {"dx_mm": 44.84, "dy_mm": 25.46},
  "employee.marital_status.widowed": {"dx_mm": 45.07, "dy_mm": 26.62},
  "employee.marital_status.separated": {"dx_mm": 39.94, "dy_mm": 27.32},
  "employee.marital_status.married": {"dx_mm": 38.77, "dy_mm": 25.69},
  "employee.marital_status.divorced": {"dx_mm": 32.46, "dy_mm": 25.69},
  "employee.has_id.yes": {"dx_mm": 28.26, "dy_mm": 25.69},
  "employee.has_id.no": {"dx_mm": 28.73, "dy_mm": 27.09},
  "employee.kibbutz_member.no": {"dx_mm": 24.76, "dy_mm": 25.69},
  "employee.kibbutz_member.income_not_transferred": {"dx_mm": 24.52, "dy_mm": 26.86},
  "employee.kibbutz_member.income_transferred": {"dx_mm": 23.12, "dy_mm": 26.39},
  "employee.mobile": {"dx_mm": 4.44, "dy_mm": 27.79},
  "employee.health_fund.name": {"dx_mm": 4.2, "dy_mm": 27.56},
  "employee.health_fund.member.no": {"dx_mm": 11.68, "dy_mm": 25.92},
  "employee.health_fund.member.yes": {"dx_mm": 11.68, "dy_mm": 26.86},
  "employee.address.city": {"dx_mm": 14.25, "dy_mm": 23.12},
  "employee.address.zip": {"dx_mm": 4.44, "dy_mm": 22.65},
  "employee.immigration_date": {"dx_mm": 7.94, "dy_mm": 20.79},
  "employee.birth_date": {"dx_mm": 14.01, "dy_mm": 20.79},
  "employee.first_name": {"dx_mm": 22.65, "dy_mm": 21.49},
  "employee.address.house_no": {"dx_mm": 19.38, "dy_mm": 21.95},
  "employee.address.street": {"dx_mm": 26.39, "dy_mm": 23.59},
  "employee.passport": {"dx_mm": 42.74, "dy_mm": 24.29},
  "employer.address": {"dx_mm": 24.99, "dy_mm": 14.71},
  "employer.phone": {"dx_mm": 14.95, "dy_mm": 15.88},
  "employer.deductions_file": {"dx_mm": 5.84, "dy_mm": 15.88},
  "income.credit_request.get_credits_elsewhere": {"dx_mm": 21.72, "dy_mm": 59.55},
  "income.other.no_pension": {"dx_mm": 21.72, "dy_mm": 55.58},
  "income.other.no_training_fund": {"dx_mm": 21.25, "dy_mm": 35.73},
  "income.main.monthly_salary": {"dx_mm": 22.19, "dy_mm": 32.23},
  "credits.1_israeli_resident": {"dx_mm": 46.24, "dy_mm": 4.44},
  "credits.2a_disability_100_or_blind": {"dx_mm": 46.71, "dy_mm": 6.07},
  "credits.2b_monthly_benefit": {"dx_mm": 45.54, "dy_mm": 7.24},
  "credits.3_eligible_locality": {"dx_mm": 47.18, "dy_mm": 8.87},
  "credits.4_new_immigrant": {"dx_mm": 46.48, "dy_mm": 11.21},
  "credits.5_spouse_no_income": {"dx_mm": 46.24, "dy_mm": 15.88},
  "credits.6_single_parent_family": {"dx_mm": 46.94, "dy_mm": 17.28},
  "credits.7_children_in_custody": {"dx_mm": 46.48, "dy_mm": 19.15},
  "credits.8_children_not_in_custody": {"dx_mm": 46.01, "dy_mm": 24.52},
  "credits.7_children_born_in_year": {"dx_mm": 32.7, "dy_mm": 21.49},
  "credits.3_from_date": {"dx_mm": 25.69, "dy_mm": 8.87},
  "credits.4_from_date": {"dx_mm": 33.4, "dy_mm": 10.98},
  "credits.3_locality_name": {"dx_mm": 33.4, "dy_mm": 10.28},
  "credits.4_no_income_until": {"dx_mm": 21.02, "dy_mm": 13.08},
  "credits.9_single_parent": {"dx_mm": 46.71, "dy_mm": 28.73},
  "credits.10_children_not_in_custody_maintenance": {"dx_mm": 47.18, "dy_mm": 31.3},
  "credits.11_disabled_child": {"dx_mm": 46.48, "dy_mm": 33.86},
  "credits.12_spousal_support": {"dx_mm": 46.24, "dy_mm": 35.03},
  "credits.13_age_16_18": {"dx_mm": 46.48, "dy_mm": 37.37},
  "credits.14_released_soldier_or_service": {"dx_mm": 46.94, "dy_mm": 38.54},
  "credits.15_graduation": {"dx_mm": 46.48, "dy_mm": 40.64},
  "credits.16_reserve_combat": {"dx_mm": 47.18, "dy_mm": 41.1},
  "credits.8_children_count_6_17": {"dx_mm": 3.74, "dy_mm": 26.86},
  "credits.7_children_count_18": {"dx_mm": 8.17, "dy_mm": 24.06},
  "credits.8_children_count_1_5": {"dx_mm": 4.67, "dy_mm": 24.99},
  "credits.7_children_count_6_17": {"dx_mm": 5.37, "dy_mm": 21.95},
  "credits.7_children_count_1_5": {"dx_mm": 89.21, "dy_mm": 25.46},
  "signature.date": {"dx_mm": 15.88, "dy_mm": 58.62},
  "signature.applicant_signature": {"dx_mm": 3.74, "dy_mm": 58.39},
  "signature.declaration": {"dx_mm": 47.18, "dy_mm": 61.42},
  "tax_coordination.approval_attached": {"dx_mm": 46.71, "dy_mm": 53.95},
  "other_income[1].payer_name": {"dx_mm": 42.51, "dy_mm": 50.68},
  "other_income[0].payer_name": {"dx_mm": 42.27, "dy_mm": 50.68},
  "other_income[1].address": {"dx_mm": 34.8, "dy_mm": 51.38},
  "other_income[0].address": {"dx_mm": 35.03, "dy_mm": 50.45},
  "other_income[1].deductions_file": {"dx_mm": 24.06, "dy_mm": 51.38},
  "other_income[0].deductions_file": {"dx_mm": 23.82, "dy_mm": 50.21},
  "other_income[1].type": {"dx_mm": 17.52, "dy_mm": 51.38},
  "other_income[0].type": {"dx_mm": 18.22, "dy_mm": 49.75},
  "other_income[1].monthly_amount": {"dx_mm": 11.68, "dy_mm": 51.38},
  "other_income[0].monthly_amount": {"dx_mm": 12.14, "dy_mm": 50.21},
  "other_income[1].tax_withheld": {"dx_mm": 5.37, "dy_mm": 51.15},
  "other_income[0].tax_withheld": {"dx_mm": 4.9, "dy_mm": 50.68},
  "tax_coordination.no_income_until_start": {"dx_mm": 46.48, "dy_mm": 44.37},
  "tax_coordination.has_additional_income": {"dx_mm": 46.48, "dy_mm": 46.71},
  "credits.16_reserve_days_prev_year": {"dx_mm": 32.0, "dy_mm": 40.87},
  "credits.14_service_start": {"dx_mm": 20.32, "dy_mm": 37.37},
  "credits.14_service_end": {"dx_mm": 7.24, "dy_mm": 37.6},
  "employment.start_date": {"dx_mm": 4.67, "dy_mm": 34.8},
}


def main():
    dry_run = "--dry-run" in sys.argv
    print("=" * 60)
    print(f"  Apply Calibration Corrections  {'[DRY RUN]' if dry_run else ''}")
    print("=" * 60)

    mapping = json.loads(MAPPING.read_text(encoding="utf-8"))
    fields  = mapping["fields"]
    print(f"\nFields in mapping : {len(fields)}")
    print(f"Corrections       : {len(CORRECTIONS)}")

    # Backup
    if not dry_run:
        backup = MAPPING.parent / f"form_101_mapping_backup_{date.today().isoformat()}.json"
        shutil.copy(MAPPING, backup)
        print(f"Backup            : {backup.name}")

    # Apply
    applied = 0
    skipped = 0
    dx_list, dy_list = [], []

    for f in fields:
        bk   = f["bindKey"]
        corr = CORRECTIONS.get(bk)
        if corr:
            dx_canvas = corr["dx_mm"] / MM
            dy_canvas = corr["dy_mm"] / MM
            old_x, old_y = f["x"], f["y"]
            f["x"] = round(old_x + dx_canvas, 2)
            f["y"] = round(old_y + dy_canvas, 2)
            dx_list.append(corr["dx_mm"])
            dy_list.append(corr["dy_mm"])
            applied += 1
            if abs(corr["dx_mm"]) > 30 or abs(corr["dy_mm"]) > 30:
                print(f"  [large] {bk}: dx={corr['dx_mm']:+.2f}mm  dy={corr['dy_mm']:+.2f}mm")
        else:
            skipped += 1

    print(f"\nApplied : {applied} fields")
    print(f"Skipped : {skipped} fields (no correction)")
    if dx_list:
        print(f"dx_mm   : min={min(dx_list):.2f}  max={max(dx_list):.2f}  avg={sum(dx_list)/len(dx_list):.2f}")
        print(f"dy_mm   : min={min(dy_list):.2f}  max={max(dy_list):.2f}  avg={sum(dy_list)/len(dy_list):.2f}")

    if not dry_run:
        MAPPING.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n✅ Mapping saved: {MAPPING.name}")
    else:
        print("\n[dry-run] No files written.")


if __name__ == "__main__":
    main()
