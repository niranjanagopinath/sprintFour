"""
Generate a realistic batch of Indian legal/administrative documents
for demonstrating the Conseal detection pipeline.

Each document contains a mix of PII types: names, Aadhaar, PAN, phone,
address, dates in context, case numbers, and relationship mentions.

Run: uv run python scripts/generate_indian_batch.py
"""

import random
import sqlite3
import uuid
import os
import sys
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "backend", "conseal.db")

# ── Data pools ──────────────────────────────────────────────────────────────

FIRST_NAMES = [
    "Rajesh", "Priya", "Amit", "Sunita", "Vikram", "Meena", "Arjun", "Kavita",
    "Suresh", "Anita", "Ravi", "Lakshmi", "Deepak", "Pooja", "Sanjay", "Geeta",
    "Ramesh", "Usha", "Ashok", "Rekha", "Mohan", "Seema", "Vinod", "Nisha",
    "Pramod", "Asha", "Santosh", "Shobha", "Mahesh", "Vandana",
]
LAST_NAMES = [
    "Sharma", "Verma", "Singh", "Patel", "Kumar", "Gupta", "Joshi", "Mishra",
    "Yadav", "Reddy", "Nair", "Menon", "Pillai", "Iyer", "Rao", "Desai",
    "Shah", "Mehta", "Chauhan", "Pandey", "Tiwari", "Dubey", "Srivastava", "Tripathi",
]
CITIES = [
    "Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai", "Kolkata",
    "Pune", "Ahmedabad", "Jaipur", "Lucknow", "Nagpur", "Indore", "Bhopal",
]
STATES = ["Maharashtra", "Delhi", "Karnataka", "Telangana", "Tamil Nadu",
          "West Bengal", "Gujarat", "Rajasthan", "Uttar Pradesh", "Madhya Pradesh"]
STREETS = [
    "14, MG Road", "Plot 7, Sector 12", "Flat 3B, Shivaji Nagar",
    "House No. 42, Gandhi Street", "A-204, Lake View Apartments",
    "22/4, Brigade Road", "Old Colony, Near Railway Station",
    "Block C, Nehru Enclave", "No. 5, Tagore Lane",
]
COURTS = [
    "District Court, {city}", "High Court of {state}", "Family Court, {city}",
    "Labour Tribunal, {city}", "Consumer Forum, {city} District",
    "Civil Court, {city}", "Fast Track Court No. 3, {city}",
]
CASE_TYPES = [
    "Civil Suit", "Matrimonial Petition", "Consumer Complaint",
    "Labour Dispute", "Property Dispute", "Maintenance Application",
    "Guardianship Petition", "Succession Certificate Application",
]
EMPLOYERS = [
    "Infosys Limited", "Tata Consultancy Services", "Wipro Technologies",
    "State Bank of India", "HDFC Bank Ltd.", "Larsen & Toubro Ltd.",
    "Reliance Industries", "HCL Technologies", "Cognizant India",
    "Mahindra & Mahindra", "Bajaj Auto Ltd.", "Indian Oil Corporation",
]
MEDICAL_CONDITIONS = [
    "Type 2 Diabetes Mellitus", "hypertension", "chronic kidney disease",
    "depressive disorder", "hypothyroidism", "asthma", "rheumatoid arthritis",
]
RELATIONSHIPS = [
    ("husband", "wife"), ("father", "daughter"), ("mother", "son"),
    ("brother", "sister"), ("employer", "employee"), ("landlord", "tenant"),
]

def rand_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

def rand_aadhaar():
    d = [random.randint(1000, 9999) for _ in range(3)]
    return f"{d[0]} {d[1]} {d[2]}"

def rand_pan():
    letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    return (
        "".join(random.choices(letters, k=5))
        + "".join(random.choices("0123456789", k=4))
        + random.choice(letters)
    )

def rand_phone():
    return f"+91 {random.randint(70,99)}{random.randint(100,999)} {random.randint(10000,99999)}"

def rand_email(name):
    parts = name.lower().split()
    domain = random.choice(["gmail.com", "yahoo.co.in", "outlook.com", "rediffmail.com"])
    return f"{parts[0]}.{parts[1]}{random.randint(1,99)}@{domain}"

def rand_address():
    return f"{random.choice(STREETS)}, {random.choice(CITIES)}, {random.choice(STATES)} – {random.randint(400001,799999)}"

def rand_date(years_back=5):
    base = datetime.now() - timedelta(days=random.randint(30, years_back*365))
    return base.strftime("%-d %B %Y")

def rand_case_no(city):
    year = random.randint(2019, 2024)
    num  = random.randint(100, 9999)
    prefix = random.choice(["CS", "MP", "WP", "CC", "LD", "FA"])
    return f"{prefix}/{num}/{year}"

def rand_amount():
    return f"₹{random.randint(10,500)*1000:,}"

def rand_court(city, state):
    tmpl = random.choice(COURTS)
    return tmpl.format(city=city, state=state)

# ── Document templates ───────────────────────────────────────────────────────

def make_affidavit(person, city, state):
    aadhaar = rand_aadhaar()
    pan     = rand_pan()
    phone   = rand_phone()
    email   = rand_email(person)
    addr    = rand_address()
    date    = rand_date(1)
    return f"""AFFIDAVIT

I, {person}, aged {random.randint(25,60)} years, residing at {addr},
do hereby solemnly affirm and state as follows:

1. I am the deponent herein and I am competent to swear this affidavit.

2. My Aadhaar number is {aadhaar} and my PAN is {pan}.

3. My mobile number is {phone} and my email address is {email}.

4. I state that the information provided by me in this application is true
   and correct to the best of my knowledge and belief.

5. I am currently employed at {random.choice(EMPLOYERS)} as a {random.choice(['Senior Analyst','Manager','Consultant','Engineer','Officer'])}.

Solemnly affirmed at {city} on {date}.

Deponent: {person}
"""

def make_court_petition(petitioner, respondent, city, state):
    case_no  = rand_case_no(city)
    court    = rand_court(city, state)
    amount   = rand_amount()
    date_fil = rand_date(2)
    date_inc = rand_date(3)
    phone_p  = rand_phone()
    addr_p   = rand_address()
    aadhaar  = rand_aadhaar()
    rel_pair = random.choice(RELATIONSHIPS)
    return f"""IN THE {court.upper()}

Case No.: {case_no}

{random.choice(CASE_TYPES).upper()}

{petitioner}                                    ... Petitioner
        versus
{respondent}                                    ... Respondent

PETITION UNDER SECTION {random.randint(9,25)} OF THE CODE OF CIVIL PROCEDURE

The petitioner {petitioner}, residing at {addr_p}, contact: {phone_p},
Aadhaar: {aadhaar}, respectfully submits:

1. The petitioner is the {rel_pair[0]} of the respondent {respondent}.

2. On {date_inc}, the respondent committed the acts complained of herein,
   causing loss to the petitioner amounting to {amount}.

3. The petitioner has been diagnosed with {random.choice(MEDICAL_CONDITIONS)}
   since {rand_date(4)}, which has been aggravated by the respondent's conduct.

4. This petition is filed within the limitation period. The cause of action
   arose on {date_inc} at {city}.

PRAYER: The petitioner prays that this Hon'ble Court be pleased to:
(a) Grant relief as prayed;
(b) Award costs of {amount};
(c) Pass such other orders as deemed fit.

Date: {date_fil}
Place: {city}

Petitioner: {petitioner}
"""

def make_kyc_form(person, city, state):
    aadhaar = rand_aadhaar()
    pan     = rand_pan()
    phone   = rand_phone()
    email   = rand_email(person)
    addr    = rand_address()
    dob     = rand_date(35)
    account = "".join([str(random.randint(0,9)) for _ in range(12)])
    ifsc    = f"SBIN{random.randint(1000,9999):04d}"
    return f"""KNOW YOUR CUSTOMER (KYC) FORM

Name of Applicant    : {person}
Date of Birth        : {dob}
Gender               : {random.choice(['Male','Female'])}
Aadhaar Number       : {aadhaar}
PAN                  : {pan}
Mobile Number        : {phone}
Email                : {email}
Residential Address  : {addr}
Bank Account No.     : {account}
IFSC Code            : {ifsc}
Annual Income        : {rand_amount()}
Source of Income     : {random.choice(['Salary','Business','Profession','Agriculture'])}
Occupation           : {random.choice(['Salaried','Self-Employed','Professional','Retired'])}

I declare that the above information is true and correct.

Signature: {person}
Date: {rand_date(1)}
"""

def make_medical_report(patient, doctor_name, city, state):
    aadhaar = rand_aadhaar()
    phone   = rand_phone()
    addr    = rand_address()
    dob     = rand_date(35)
    cond    = random.choice(MEDICAL_CONDITIONS)
    date_adm = rand_date(1)
    return f"""MEDICAL FITNESS CERTIFICATE

Patient Name    : {patient}
Date of Birth   : {dob}
Aadhaar No.     : {aadhaar}
Contact         : {phone}
Address         : {addr}

Examined by Dr. {doctor_name}, {random.choice(['MBBS','MD','MS','DM'])},
Reg. No.: MCI-{random.randint(10000,99999)}

Date of Examination: {date_adm}

CLINICAL FINDINGS:
The above-named patient was examined on {date_adm}.

Diagnosis: The patient presents with {cond} since {rand_date(4)}.
Current Medications: {random.choice(['Metformin 500mg','Amlodipine 5mg','Levothyroxine 50mcg','Pantoprazole 40mg'])},
                     {random.choice(['Aspirin 75mg','Atorvastatin 10mg','Losartan 25mg','Montelukast 10mg'])}.

Blood Pressure: {random.randint(110,140)}/{random.randint(70,90)} mmHg
Blood Sugar (Fasting): {random.randint(90,200)} mg/dL

The patient is {random.choice(['fit','unfit','conditionally fit'])} for employment.

Dr. {doctor_name}
{city}, {state}
"""

def make_employment_letter(employee, city, state):
    employer   = random.choice(EMPLOYERS)
    aadhaar    = rand_aadhaar()
    pan        = rand_pan()
    phone      = rand_phone()
    email      = rand_email(employee)
    addr       = rand_address()
    salary     = rand_amount()
    join_date  = rand_date(5)
    return f"""EMPLOYMENT VERIFICATION LETTER

Date: {rand_date(0)}

To Whom It May Concern,

This is to certify that {employee} is employed with {employer}
as {random.choice(['Software Engineer','Project Manager','Business Analyst','Team Lead','Senior Developer'])}
since {join_date}.

Employee Details:
  Full Name    : {employee}
  Aadhaar No.  : {aadhaar}
  PAN          : {pan}
  Contact      : {phone}
  Email        : {email}
  Address      : {addr}
  Monthly CTC  : {salary}

The employee has been performing satisfactorily. This letter is issued
at the request of {employee} for official purposes.

For {employer},

HR Department
{city}, {state}
"""

# ── Generator ────────────────────────────────────────────────────────────────

TEMPLATES = [
    make_affidavit,
    make_court_petition,
    make_kyc_form,
    make_medical_report,
    make_employment_letter,
]

def make_document(i):
    person1 = rand_name()
    person2 = rand_name()
    city    = random.choice(CITIES)
    state   = random.choice(STATES)

    template = TEMPLATES[i % len(TEMPLATES)]
    if template == make_court_petition:
        text = template(person1, person2, city, state)
        title = f"Court_Petition_{i+1:03d}.txt"
    elif template == make_medical_report:
        doctor = rand_name()
        text   = template(person1, doctor, city, state)
        title  = f"Medical_Report_{i+1:03d}.txt"
    else:
        text  = template(person1, city, state)
        tname = template.__name__.replace("make_", "").replace("_", " ").title().replace(" ", "_")
        title = f"{tname}_{i+1:03d}.txt"

    return title, text


def main(count=20):
    if not os.path.exists(DB_PATH):
        print(f"DB not found at {DB_PATH}. Start the backend first to create it.", file=sys.stderr)
        sys.exit(1)

    batch_id = f"batch-synthetic-{uuid.uuid4().hex[:6]}"
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    inserted = 0
    for i in range(count):
        title, text = make_document(i)
        doc_id = f"doc-{uuid.uuid4().hex[:8]}"
        conn.execute(
            """INSERT INTO documents
               (id, title, raw_text, state, source_type, file_type, ocr_used, batch_id)
               VALUES (?, ?, ?, 'pending', 'synthetic', 'text', 0, ?)""",
            (doc_id, title, text, batch_id),
        )
        inserted += 1

    conn.commit()
    conn.close()
    print(f"Inserted {inserted} documents (batch_id={batch_id})")
    print("Restart the backend or call /documents to see them.")


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    main(count)
