"""Generates realistic synthetic Indian legal documents for demo/testing."""

import random
from datetime import datetime, timedelta

FIRST_NAMES = [
    "Rajesh","Priya","Amit","Sunita","Vikram","Meena","Arjun","Kavita",
    "Suresh","Anita","Ravi","Lakshmi","Deepak","Pooja","Sanjay","Geeta",
    "Ramesh","Usha","Ashok","Rekha","Mohan","Seema","Vinod","Nisha",
]
LAST_NAMES = [
    "Sharma","Verma","Singh","Patel","Kumar","Gupta","Joshi","Mishra",
    "Yadav","Reddy","Nair","Menon","Iyer","Rao","Desai","Shah","Mehta",
    "Chauhan","Pandey","Tiwari","Dubey","Srivastava",
]
CITIES  = ["Mumbai","Delhi","Bengaluru","Hyderabad","Chennai","Kolkata","Pune","Ahmedabad","Jaipur","Lucknow"]
STATES  = ["Maharashtra","Delhi","Karnataka","Telangana","Tamil Nadu","West Bengal","Gujarat","Rajasthan","Uttar Pradesh"]
STREETS = [
    "14, MG Road","Plot 7, Sector 12","Flat 3B, Shivaji Nagar",
    "House No. 42, Gandhi Street","A-204, Lake View Apartments",
    "22/4, Brigade Road","Block C, Nehru Enclave","No. 5, Tagore Lane",
]
EMPLOYERS = [
    "Infosys Limited","Tata Consultancy Services","Wipro Technologies",
    "State Bank of India","HDFC Bank Ltd.","Larsen & Toubro Ltd.",
    "Reliance Industries","HCL Technologies","Cognizant India",
]
COURTS = [
    "District Court, {city}","High Court of {state}","Family Court, {city}",
    "Labour Tribunal, {city}","Consumer Forum, {city} District",
]
CASE_TYPES  = ["Civil Suit","Matrimonial Petition","Consumer Complaint","Labour Dispute","Property Dispute"]
MEDICAL     = ["Type 2 Diabetes Mellitus","hypertension","chronic kidney disease","depressive disorder","hypothyroidism"]
ROLES       = ["Senior Analyst","Manager","Consultant","Engineer","Officer","Team Lead","Business Analyst"]


def _name():  return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
def _aadhaar(): return f"{random.randint(2000,9999)} {random.randint(1000,9999)} {random.randint(1000,9999)}"
def _pan():
    L = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    return "".join(random.choices(L,k=5)) + "".join(random.choices("0123456789",k=4)) + random.choice(L)
def _phone():  return f"+91 {random.randint(70,99)}{random.randint(100,999)} {random.randint(10000,99999)}"
def _email(n): p=n.lower().split(); d=random.choice(["gmail.com","yahoo.co.in","outlook.com"]); return f"{p[0]}.{p[1]}{random.randint(1,99)}@{d}"
def _addr():   return f"{random.choice(STREETS)}, {random.choice(CITIES)}, {random.choice(STATES)} – {random.randint(400001,799999)}"
def _date(yb=2): base=datetime.now()-timedelta(days=random.randint(1, max(1, yb*365))); return base.strftime("%d %B %Y").lstrip("0")
def _amount(): return f"₹{random.randint(10,500)*1000:,}"
def _account(): return "".join([str(random.randint(0,9)) for _ in range(12)])
def _ifsc():   return f"SBIN{random.randint(1000,9999):04d}"
def _court(city,state): return random.choice(COURTS).format(city=city,state=state)


def _affidavit(city, state):
    p = _name()
    return f"Affidavit_{p.replace(' ','_')}.txt", f"""AFFIDAVIT

I, {p}, aged {random.randint(25,60)} years, residing at {_addr()},
do hereby solemnly affirm and state as follows:

1. I am the deponent herein and am competent to swear this affidavit.
2. My Aadhaar number is {_aadhaar()} and my PAN is {_pan()}.
3. My mobile number is {_phone()} and my email is {_email(p)}.
4. I am currently employed at {random.choice(EMPLOYERS)} as {random.choice(ROLES)}.
5. All information provided herein is true to the best of my knowledge.

Solemnly affirmed at {city} on {_date(1)}.
Deponent: {p}
"""


def _petition(city, state):
    p1, p2 = _name(), _name()
    case_no = f"CS/{random.randint(100,9999)}/{random.randint(2019,2024)}"
    return f"Court_Petition_{p1.split()[1]}.txt", f"""IN THE {_court(city,state).upper()}

Case No.: {case_no}
{random.choice(CASE_TYPES).upper()}

{p1}  ...Petitioner  vs  {p2}  ...Respondent

The petitioner {p1}, residing at {_addr()}, contact: {_phone()},
Aadhaar: {_aadhaar()}, respectfully submits:

1. The petitioner is the husband/wife of the respondent {p2}.
2. On {_date(3)}, the respondent caused loss amounting to {_amount()}.
3. The petitioner has suffered from {random.choice(MEDICAL)} since {_date(4)},
   aggravated by the respondent's conduct.
4. This petition is filed within limitation. Cause of action arose at {city}.

PRAYER: Award relief of {_amount()} and costs.

Date: {_date(1)}  |  Place: {city}
Petitioner: {p1}
"""


def _kyc(city, state):
    p = _name()
    return f"KYC_Form_{p.replace(' ','_')}.txt", f"""KNOW YOUR CUSTOMER (KYC) FORM

Name                 : {p}
Date of Birth        : {_date(35)}
Aadhaar Number       : {_aadhaar()}
PAN                  : {_pan()}
Mobile Number        : {_phone()}
Email                : {_email(p)}
Residential Address  : {_addr()}
Bank Account No.     : {_account()}
IFSC Code            : {_ifsc()}
Annual Income        : {_amount()}
Source of Income     : {random.choice(['Salary','Business','Profession'])}

I declare that the above information is true and correct.

Signature: {p}
Date: {_date(1)}
"""


def _medical(city, state):
    patient = _name()
    doctor  = _name()
    return f"Medical_Report_{patient.split()[1]}.txt", f"""MEDICAL FITNESS CERTIFICATE

Patient Name    : {patient}
Date of Birth   : {_date(35)}
Aadhaar No.     : {_aadhaar()}
Contact         : {_phone()}
Address         : {_addr()}

Examined by Dr. {doctor}, {random.choice(['MBBS','MD','MS'])},
Reg. No.: MCI-{random.randint(10000,99999)}

Date of Examination: {_date(1)}

Diagnosis: The patient presents with {random.choice(MEDICAL)} since {_date(4)}.
Current Medications: {random.choice(['Metformin 500mg','Amlodipine 5mg','Levothyroxine 50mcg'])}.

Blood Pressure: {random.randint(110,140)}/{random.randint(70,90)} mmHg
Blood Sugar (Fasting): {random.randint(90,200)} mg/dL

The patient is {random.choice(['fit','unfit','conditionally fit'])} for employment.

Dr. {doctor}
{city}, {state}
"""


def _employment(city, state):
    emp = _name()
    return f"Employment_Letter_{emp.replace(' ','_')}.txt", f"""EMPLOYMENT VERIFICATION LETTER

Date: {_date(0)}

This is to certify that {emp} is employed with {random.choice(EMPLOYERS)}
as {random.choice(ROLES)} since {_date(5)}.

  Aadhaar No.  : {_aadhaar()}
  PAN          : {_pan()}
  Contact      : {_phone()}
  Email        : {_email(emp)}
  Address      : {_addr()}
  Monthly CTC  : {_amount()}
  Bank Account : {_account()}
  IFSC         : {_ifsc()}

The employee's UPI ID: {emp.lower().replace(' ','.')}{random.randint(1,9)}@okicici

This letter is issued at the request of {emp} for official purposes.

For HR Department
{city}, {state}
"""


_TEMPLATES = [_affidavit, _petition, _kyc, _medical, _employment]


def make_document(i: int):
    """Return (title, text) for document index i."""
    city  = random.choice(CITIES)
    state = random.choice(STATES)
    fn    = _TEMPLATES[i % len(_TEMPLATES)]
    return fn(city, state)
