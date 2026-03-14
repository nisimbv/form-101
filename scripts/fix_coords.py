"""
fix_coords.py – Apply coordinate corrections to PDFTemplate_v6.html
based on field_positions.json extracted from form101_REAL_ORIGINAL_FILLED.pdf
"""
import sys, os

path = r'C:\Users\Admin\form101_v6_files\PDFTemplate_v6.html'

with open(path, 'r', encoding='utf-8') as f:
    c = f.read()

original = c  # for diff check at end

# ─────────────────────────────────────────────
# Helper: replace exactly one occurrence (raises if 0 or >1 found)
# ─────────────────────────────────────────────
def rep(old, new):
    global c
    count = c.count(old)
    if count == 0:
        print(f'  ⚠ NOT FOUND: {old[:60]!r}')
        return
    if count > 1:
        print(f'  ⚠ MULTIPLE ({count}) occurrences: {old[:60]!r}')
    c = c.replace(old, new)
    print(f'  ✓ {old[:60]!r}')

print('=== PAGE 1 – Employee text fields (Section B) ===')

# last_name
rep(
    'left:137mm; top:78.8mm; width:46mm; text-align:right;"><?= s(data.last_name)',
    'left:139mm; top:80.8mm; width:44mm; text-align:right;"><?= s(data.last_name)'
)
# first_name
rep(
    'left:111mm; top:78.8mm; width:24mm; text-align:right;"><?= s(data.first_name)',
    'left:98mm;  top:80.8mm; width:41mm; text-align:right;"><?= s(data.first_name)'
)
# id_number / passport
rep(
    'left:48mm; top:78.8mm; width:55mm; text-align:center;"><?= s(data.id_number || data.passport_number)',
    'left:183mm; top:80.8mm; width:24mm; text-align:center;"><?= s(data.id_number || data.passport_number)'
)
# birth_date
rep(
    'left:138mm; top:89.8mm; width:54mm; text-align:center;"><?= dmy(data.birth_date)',
    'left:58.6mm; top:80.8mm; width:36mm; text-align:center;"><?= dmy(data.birth_date)'
)
# aliya_date
rep(
    'left:101mm; top:89.8mm; width:32mm; text-align:center;"><?= dmy(data.aliya_date)',
    'left:26.4mm; top:80.8mm; width:32mm; text-align:center;"><?= dmy(data.aliya_date)'
)
# address
rep(
    'left:87mm; top:100.9mm; width:104mm; text-align:right;"><?= s(data.address)',
    'left:80mm;  top:89mm;   width:80mm;  text-align:right;"><?= s(data.address)'
)
# postal_code
rep(
    'left:48mm; top:100.9mm; width:33mm; text-align:center;"><?= s(data.postal_code)',
    'left:10mm; top:89mm;    width:32mm; text-align:center;"><?= s(data.postal_code)'
)
# email
rep(
    'left:89mm; top:112.1mm; width:102mm; text-align:right;"><?= s(data.email)',
    'left:163mm; top:108.3mm; width:35mm; text-align:right;"><?= s(data.email)'
)
# mobile_phone
rep(
    'left:47mm; top:112.1mm; width:34mm; text-align:center;"><?= s(data.mobile_phone)',
    'left:52.6mm; top:108.3mm; width:35mm; text-align:center;"><?= s(data.mobile_phone)'
)

print()
print('=== PAGE 1 – Section B: Gender checkboxes ===')
rep("left:34.5mm; top:121.0mm", "left:187.1mm; top:100.9mm")  # זכר
rep("left:34.5mm; top:126.8mm", "left:187.1mm; top:105.4mm")  # נקבה

print()
print('=== PAGE 1 – Section B: Marital status ===')
rep("left:46.5mm; top:121.0mm", "left:173.3mm; top:100.3mm")  # רווק/ה
rep("left:58.7mm; top:121.0mm", "left:152.5mm; top:100.3mm")  # נשוי/אה
rep("left:46.5mm; top:126.8mm", "left:128.8mm; top:100.3mm")  # גרוש/ה
rep("left:58.7mm; top:126.8mm", "left:173.4mm; top:105.0mm")  # אלמן/ה
rep("left:70.5mm; top:126.8mm", "left:156.8mm; top:105.0mm")  # פרוד/ה

print()
print('=== PAGE 1 – Section B: Israeli resident ===')
rep("left:81.7mm; top:121.0mm", "left:108.8mm; top:101.2mm")  # כן
rep("left:81.7mm; top:126.8mm", "left:96.2mm;  top:100.5mm")  # לא

print()
print('=== PAGE 1 – Section B: Kibbutz member ===')
rep("left:103.2mm; top:121.0mm", "left:88.4mm; top:100.5mm")  # כן
rep("left:103.2mm; top:126.8mm", "left:96.2mm; top:105.1mm")  # לא

print()
print('=== PAGE 1 – Section D: Start date field ===')
rep(
    'left:13mm; top:124.0mm; width:24mm; text-align:center;"><?= dmy(data.start_date)',
    'left:10mm; top:123mm;   width:30mm; text-align:center;"><?= dmy(data.start_date)'
)

print()
print('=== PAGE 1 – Section D: Income type checkboxes ===')
rep("left:83mm; top:125.5mm", "left:84.7mm; top:128.4mm")  # חודשית
rep("left:83mm; top:131.0mm", "left:84.7mm; top:132.6mm")  # נוספת
rep("left:83mm; top:135.2mm", "left:84.7mm; top:136.8mm")  # חלקית
rep("left:83mm; top:139.4mm", "left:84.7mm; top:141.2mm")  # יומי
rep("left:83mm; top:143.7mm", "left:84.7mm; top:145.3mm")  # קצבה
rep("left:83mm; top:147.9mm", "left:84.7mm; top:149.5mm")  # מלגה

print()
print('=== PAGE 1 – Section C: Children table ===')
rep(
    "var y = 140.0 + (i*11.65)",
    "var y = 131.4 + (i*7.65)"
)
# name column: 145mm→170.7mm, width 28mm→13mm
rep(
    'left:145mm; top:<?= y ?>mm; width:28mm; text-align:right;"><?= s(c.name)',
    'left:170.7mm; top:<?= y ?>mm; width:13mm; text-align:right;"><?= s(c.name)'
)
# id column: 114mm→133.7mm, width 28mm→25mm
rep(
    'left:114mm; top:<?= y ?>mm; width:28mm; text-align:center;"><?= s(c.id)',
    'left:133.7mm; top:<?= y ?>mm; width:25mm; text-align:center;"><?= s(c.id)'
)
# birth_date column: 95mm→99.8mm, width 16mm→34mm
rep(
    'left:95mm; top:<?= y ?>mm; width:16mm; text-align:center;"><?= dmy(c.birth_date)',
    'left:99.8mm; top:<?= y ?>mm; width:34mm; text-align:center;"><?= dmy(c.birth_date)'
)
# in_custody checkbox: left:176.6mm→186.9mm
rep("left:176.6mm; top:<?= y-1.6 ?>mm", "left:186.9mm; top:<?= y-1.6 ?>mm")
# receives_allowance: left:183.5mm→184.4mm (small change)
rep("left:183.5mm; top:<?= y-1.6 ?>mm", "left:184.4mm; top:<?= y-1.6 ?>mm")
# reduce max children from 10 to 6
rep("i<10", "i<6")

print()
print('=== PAGE 1 – Section E: Other income checkboxes (2-column layout) ===')
old_e = """\
  <? if (!data.has_other_income) { ?><div class="mark" style="left:84mm; top:177.7mm;">✓</div><? } ?>
  <? if (data.has_other_income) { ?><div class="mark" style="left:84mm; top:183.6mm;">✓</div><? } ?>
  <? if (flags.other_income_monthly) { ?><div class="mark" style="left:72mm; top:188.8mm;">✓</div><? } ?>
  <? if (flags.other_income_additional) { ?><div class="mark" style="left:72mm; top:194.5mm;">✓</div><? } ?>
  <? if (flags.other_income_partial) { ?><div class="mark" style="left:72mm; top:200.2mm;">✓</div><? } ?>
  <? if (flags.other_income_daily) { ?><div class="mark" style="left:72mm; top:205.8mm;">✓</div><? } ?>
  <? if (flags.other_income_pension) { ?><div class="mark" style="left:72mm; top:209.5mm;">✓</div><? } ?>
  <? if (flags.other_income_scholarship) { ?><div class="mark" style="left:72mm; top:213.3mm;">✓</div><? } ?>
  <? if (flags.no_study_fund_other) { ?><div class="mark" style="left:11.2mm; top:219.8mm;">✓</div><? } ?>
  <? if (flags.no_pension_other) { ?><div class="mark" style="left:11.2mm; top:226.2mm;">✓</div><? } ?>"""
new_e = """\
  <? if (!data.has_other_income) { ?><div class="mark" style="left:84.2mm; top:162.4mm;">✓</div><? } ?>
  <? if (data.has_other_income) { ?><div class="mark" style="left:84.2mm; top:171.0mm;">✓</div><? } ?>
  <? if (flags.other_income_monthly) { ?><div class="mark" style="left:84.2mm; top:175.4mm;">✓</div><? } ?>
  <? if (flags.other_income_daily) { ?><div class="mark" style="left:42.6mm; top:175.4mm;">✓</div><? } ?>
  <? if (flags.other_income_additional) { ?><div class="mark" style="left:84.2mm; top:179.2mm;">✓</div><? } ?>
  <? if (flags.other_income_pension) { ?><div class="mark" style="left:42.6mm; top:179.2mm;">✓</div><? } ?>
  <? if (flags.other_income_partial) { ?><div class="mark" style="left:84.2mm; top:183.1mm;">✓</div><? } ?>
  <? if (flags.other_income_scholarship) { ?><div class="mark" style="left:42.6mm; top:183.1mm;">✓</div><? } ?>
  <? if (flags.no_study_fund_other) { ?><div class="mark" style="left:83.9mm; top:208.1mm;">✓</div><? } ?>
  <? if (flags.no_pension_other) { ?><div class="mark" style="left:83.7mm; top:220.3mm;">✓</div><? } ?>"""
rep(old_e, new_e)

print()
print('=== PAGE 1 – Section E: Additional income table ===')
old_inc1 = """\
  <? for (var i=0; i<3; i++) { var inc = incAt(i); var y2 = 231.2 + (i*7.4); ?>
    <div class="field tiny" style="left:56mm; top:<?= y2 ?>mm; width:20mm; text-align:center;"><?= s(inc.tax) ?></div>
    <div class="field tiny" style="left:77mm; top:<?= y2 ?>mm; width:17mm; text-align:center;"><?= s(inc.amount) ?></div>
    <div class="field tiny" style="left:95mm; top:<?= y2 ?>mm; width:25mm; text-align:center;"><?= s(inc.type) ?></div>
    <div class="field tiny" style="left:123mm; top:<?= y2 ?>mm; width:30mm; text-align:center;"><?= s(inc.address) ?></div>
    <div class="field tiny" style="left:155mm; top:<?= y2 ?>mm; width:36mm; text-align:right;"><?= s(inc.employer) ?></div>
  <? } ?>"""
new_inc1 = """\
  <? for (var i=0; i<3; i++) { var inc = incAt(i); var y2 = 222.0 + (i*5.0); ?>
    <div class="field tiny" style="left:9mm;   top:<?= y2 ?>mm; width:26mm; text-align:center;"><?= s(inc.tax) ?></div>
    <div class="field tiny" style="left:35mm;  top:<?= y2 ?>mm; width:26mm; text-align:center;"><?= s(inc.amount) ?></div>
    <div class="field tiny" style="left:61mm;  top:<?= y2 ?>mm; width:20mm; text-align:center;"><?= s(inc.type) ?></div>
    <div class="field tiny" style="left:81mm;  top:<?= y2 ?>mm; width:28mm; text-align:center;"><?= s(inc.tax_id || '') ?></div>
    <div class="field tiny" style="left:109mm; top:<?= y2 ?>mm; width:48mm; text-align:right;"><?= s(inc.employer) ?> <?= s(inc.address) ?></div>
  <? } ?>"""
rep(old_inc1, new_inc1)

print()
print('=== PAGE 1 – Section F: Spouse fields ===')
old_spouse_fields = """\
  <div class="field tiny" style="left:132mm; top:254.7mm; width:34mm; text-align:right;"><?= s(data.spouse_last_name) ?> <?= s(data.spouse_first_name) ?></div>
  <div class="field tiny" style="left:168mm; top:254.7mm; width:24mm; text-align:center;"><?= s(data.spouse_id_number || data.spouse_passport_number) ?></div>
  <div class="field tiny" style="left:132mm; top:262.0mm; width:29mm; text-align:center;"><?= dmy(data.spouse_birth_date) ?></div>
  <div class="field tiny" style="left:100mm; top:262.0mm; width:24mm; text-align:center;"><?= dmy(data.spouse_aliya_date) ?></div>"""
new_spouse_fields = """\
  <div class="field tiny" style="left:140mm; top:248mm; width:42mm; text-align:right;"><?= s(data.spouse_last_name) ?></div>
  <div class="field tiny" style="left:103mm; top:248mm; width:37mm; text-align:right;"><?= s(data.spouse_first_name) ?></div>
  <div class="field tiny" style="left:184mm; top:248mm; width:23mm; text-align:center;"><?= s(data.spouse_id_number || data.spouse_passport_number) ?></div>
  <div class="field tiny" style="left:66mm;  top:248mm; width:34mm; text-align:center;"><?= dmy(data.spouse_birth_date) ?></div>
  <div class="field tiny" style="left:33mm;  top:248mm; width:32mm; text-align:center;"><?= dmy(data.spouse_aliya_date) ?></div>"""
rep(old_spouse_fields, new_spouse_fields)

print()
print('=== PAGE 1 – Section F: Spouse checkboxes ===')
rep("left:90mm;   top:258.6mm",  "left:145.3mm; top:255.1mm")   # !has_spouse  (אין)
rep("left:90mm; top:258.6mm",    "left:145.3mm; top:255.1mm")   # fallback if spaces differ
rep("left:118.6mm; top:258.6mm", "left:100.4mm; top:255.2mm")   # has_spouse   (יש)
rep("left:61.5mm; top:258.7mm",  "left:145.3mm; top:255.1mm")   # spouse_no_income = לא
rep("left:44.5mm; top:258.7mm",  "left:57.2mm;  top:255.2mm")   # spouse_work = עבודה
rep("left:21.2mm; top:258.7mm",  "left:29.2mm;  top:255.2mm")   # spouse_other = אחר

print()
print('=== PAGE 1 – Section Z: Changes table (correct column order + row positions) ===')
old_z = """\
  <? for (var i=0; i<3; i++) { var ch = chgAt(i); var y3 = 283.2 + (i*4.0); ?>
    <div class="field tiny" style="left:7mm; top:<?= y3 ?>mm; width:19mm; text-align:center;"><?= dmy(ch.notification_date) ?></div>
    <div class="field tiny" style="left:29mm; top:<?= y3 ?>mm; width:87mm; text-align:right; white-space:normal;"><?= s(ch.details) ?></div>
    <div class="field tiny" style="left:119mm; top:<?= y3 ?>mm; width:18mm; text-align:center;"><?= dmy(ch.date) ?></div>
    <div class="field tiny" style="left:164mm; top:<?= y3 ?>mm; width:30mm; text-align:right;"><?= s(ch.signature) ?></div>
  <? } ?>"""
new_z = """\
  <? for (var i=0; i<3; i++) { var ch = chgAt(i); var y3 = 274.4 + (i*9.0); ?>
    <div class="field tiny" style="left:10mm;  top:<?= y3 ?>mm; width:30mm;  text-align:right;"><?= s(ch.signature) ?></div>
    <div class="field tiny" style="left:41mm;  top:<?= y3 ?>mm; width:25mm;  text-align:center;"><?= dmy(ch.notification_date) ?></div>
    <div class="field tiny" style="left:67mm;  top:<?= y3 ?>mm; width:103mm; text-align:right; white-space:normal;"><?= s(ch.details) ?></div>
    <div class="field tiny" style="left:170mm; top:<?= y3 ?>mm; width:21mm;  text-align:center;"><?= dmy(ch.date) ?></div>
  <? } ?>"""
rep(old_z, new_z)

print()
print('=== PAGE 2 – Section H: Relief checkboxes (left 188.7→181mm, tops corrected) ===')
# All Section H marks currently at left:188.7mm.
# We correct each individually to catch top values too.
rep('left:188.7mm; top:16.5mm',  'left:181mm; top:16.5mm')   # h1 resident (top already OK)
rep('left:188.7mm; top:23.6mm',  'left:181mm; top:21.7mm')   # h2a disabled
rep('left:188.7mm; top:33.0mm',  'left:181mm; top:29.4mm')   # h2b allowance
rep('left:188.7mm; top:40.4mm',  'left:181mm; top:35.3mm')   # h3 settlement
rep('left:188.7mm; top:49.8mm',  'left:181mm; top:45.1mm')   # h4 new immigrant
rep('left:188.7mm; top:68.0mm',  'left:181mm; top:59.3mm')   # h5 spouse
rep('left:188.7mm; top:78.0mm',  'left:181mm; top:67.2mm')   # h6 single parent
rep('left:188.7mm; top:87.6mm',  'left:181mm; top:75.3mm')   # h7 children custody
rep('left:188.7mm; top:110.8mm', 'left:181mm; top:95.9mm')   # h8 children general
rep('left:188.7mm; top:131.8mm', 'left:181mm; top:113.4mm')  # h9 sole parent
rep('left:188.7mm; top:139.4mm', 'left:181mm; top:119.6mm')  # h10 not custody
rep('left:188.7mm; top:148.7mm', 'left:181mm; top:127.0mm')  # h11 disabled children (estimated)
rep('left:188.7mm; top:159.5mm', 'left:181mm; top:137.2mm')  # h12 alimony
rep('left:188.7mm; top:167.6mm', 'left:181mm; top:142.3mm')  # h13 age 16-18
rep('left:188.7mm; top:175.2mm', 'left:181mm; top:147.6mm')  # h14 discharged soldier
rep('left:188.7mm; top:191.0mm', 'left:181mm; top:156.1mm')  # h15 academic
rep('left:188.7mm; top:198.8mm', 'left:181mm; top:160.9mm')  # h16 reserve
rep('left:188.7mm; top:206.4mm', 'left:181mm; top:165.5mm')  # h17 no income (estimated)

print()
print('=== PAGE 2 – Section T: Tax coordination ===')
rep('left:188.7mm; top:219.3mm', 'left:181.5mm; top:171.9mm')  # t1 no prior income
rep('left:188.7mm; top:231.0mm', 'left:181.5mm; top:182.1mm')  # t2 has other income
rep('left:188.7mm; top:258.5mm', 'left:181.5mm; top:210.1mm')  # t3 assessor approved

print()
print('=== PAGE 2 – Section T: Additional income table ===')
old_inc2 = """\
  <? for (var i=0; i<3; i++) { var inc2 = incAt(i); var yy = 240.7 + (i*7.1); ?>
    <div class="field tiny" style="left:143mm; top:<?= yy ?>mm; width:40mm; text-align:right;"><?= s(inc2.employer) ?></div>
    <div class="field tiny" style="left:104mm; top:<?= yy ?>mm; width:34mm; text-align:right;"><?= s(inc2.address) ?></div>
    <div class="field tiny" style="left:76mm; top:<?= yy ?>mm; width:24mm; text-align:center;"><?= s(inc2.tax) ?></div>
    <div class="field tiny" style="left:49mm; top:<?= yy ?>mm; width:24mm; text-align:center;"><?= s(inc2.type) ?></div>
    <div class="field tiny" style="left:23mm; top:<?= yy ?>mm; width:22mm; text-align:center;"><?= s(inc2.amount) ?></div>
    <div class="field tiny" style="left:3mm; top:<?= yy ?>mm; width:16mm; text-align:center;"><?= s(inc2.tax_amount || '') ?></div>
  <? } ?>"""
new_inc2 = """\
  <? for (var i=0; i<3; i++) { var inc2 = incAt(i); var yy = 195.1 + (i*5.05); ?>
    <div class="field tiny" style="left:109mm; top:<?= yy ?>mm; width:48mm; text-align:right;"><?= s(inc2.employer) ?> <?= s(inc2.address) ?></div>
    <div class="field tiny" style="left:81mm;  top:<?= yy ?>mm; width:27mm; text-align:center;"><?= s(inc2.tax) ?></div>
    <div class="field tiny" style="left:61mm;  top:<?= yy ?>mm; width:20mm; text-align:center;"><?= s(inc2.type) ?></div>
    <div class="field tiny" style="left:35mm;  top:<?= yy ?>mm; width:26mm; text-align:center;"><?= s(inc2.amount) ?></div>
    <div class="field tiny" style="left:9mm;   top:<?= yy ?>mm; width:26mm; text-align:center;"><?= s(inc2.tax_amount || '') ?></div>
  <? } ?>"""
rep(old_inc2, new_inc2)

print()
print('=== PAGE 2 – Declaration ===')
rep('left:188.7mm; top:267.8mm',  'left:181mm; top:220mm')    # confirm checkbox
rep('left:84mm; top:274.6mm; width:28mm',
    'left:55mm; top:231.2mm; width:40mm')                      # declaration_date
rep('left:126mm; top:274.6mm; width:36mm',
    'left:100mm; top:231.2mm; width:60mm')                     # name in declaration
rep('left:27mm; top:268.4mm',  'left:9mm; top:235mm')         # signature image

print()
# ─────────────────────────────────────────────
# Write output
# ─────────────────────────────────────────────
if c == original:
    print('⚠  No changes were made!')
    sys.exit(1)

with open(path, 'w', encoding='utf-8') as f:
    f.write(c)

changed = sum(1 for a, b in zip(original.split('\n'), c.split('\n')) if a != b)
print(f'\n✅  Done – {changed} lines changed, file written.')
