"""
Management command: seed_reference_data

Re-seeds all reference / configuration data that was delivered via Django
data migrations but is not re-applied if those rows are deleted at runtime.

Run:  python manage.py seed_reference_data
"""
from django.core.management.base import BaseCommand
from django.db import transaction


# ── States & Cities ────────────────────────────────────────────────────────────

STATES_AND_CITIES = [
    ('Andhra Pradesh',        'AP', ['Visakhapatnam','Vijayawada','Guntur','Nellore','Kurnool','Tirupati','Kadapa','Rajahmundry','Anantapur','Chittoor','Eluru','Ongole','Srikakulam','Vizianagaram','Machilipatnam','Chirala','Adoni','Tenali','Proddatur','Nandyal','Hindupur']),
    ('Arunachal Pradesh',     'AR', ['Itanagar','Naharlagun','Pasighat','Tawang','Ziro','Bomdila']),
    ('Assam',                 'AS', ['Guwahati','Dibrugarh','Silchar','Jorhat','Tezpur','Nagaon','Tinsukia','Karimganj','Sivasagar','Goalpara','Barpeta','Dhubri','Diphu','North Lakhimpur']),
    ('Bihar',                 'BR', ['Patna','Gaya','Bhagalpur','Muzaffarpur','Purnia','Arrah','Darbhanga','Bihar Sharif','Katihar','Munger','Chapra','Begusarai','Bettiah','Motihari','Siwan','Sasaram','Hajipur','Nawada','Samastipur','Gopalganj']),
    ('Chhattisgarh',          'CG', ['Raipur','Bhilai','Durg','Bilaspur','Korba','Rajnandgaon','Jagdalpur','Ambikapur','Dhamtari','Raigarh']),
    ('Goa',                   'GA', ['Panaji','Margao','Vasco da Gama','Mapusa','Ponda','Bicholim']),
    ('Gujarat',               'GJ', ['Ahmedabad','Surat','Vadodara','Rajkot','Bhavnagar','Jamnagar','Junagadh','Gandhinagar','Anand','Nadiad','Morbi','Mehsana','Bharuch','Navsari','Valsad','Porbandar','Godhra','Patan','Surendranagar']),
    ('Haryana',               'HR', ['Faridabad','Gurgaon','Hisar','Rohtak','Panipat','Karnal','Ambala','Yamunanagar','Sonipat','Kurukshetra','Bhiwani','Sirsa','Jind','Kaithal','Rewari','Palwal','Fatehabad']),
    ('Himachal Pradesh',      'HP', ['Shimla','Dharamsala','Manali','Mandi','Solan','Kullu','Una','Bilaspur','Hamirpur','Chamba','Nahan']),
    ('Jharkhand',             'JH', ['Ranchi','Jamshedpur','Dhanbad','Bokaro','Deoghar','Hazaribagh','Giridih','Ramgarh','Dumka','Chaibasa','Phusro']),
    ('Karnataka',             'KA', ['Bengaluru','Mysuru','Mangaluru','Hubli','Belagavi','Shivamogga','Davanagere','Ballari','Kalaburagi','Tumakuru','Chikkamagaluru','Udupi','Chitradurga','Bidar','Hassan','Kolar','Mandya','Raichur','Bagalkot','Koppal','Haveri','Vijayapura','Gadag']),
    ('Kerala',                'KL', ['Thiruvananthapuram','Kochi','Kozhikode','Thrissur','Kollam','Kannur','Alappuzha','Palakkad','Malappuram','Kottayam','Pathanamthitta','Idukki','Kalpetta','Kasaragod']),
    ('Madhya Pradesh',        'MP', ['Bhopal','Indore','Jabalpur','Gwalior','Ujjain','Ratlam','Sagar','Satna','Rewa','Dewas','Khandwa','Chhindwara','Vidisha','Guna','Shivpuri','Damoh','Singrauli','Burhanpur']),
    ('Maharashtra',           'MH', ['Mumbai','Pune','Nagpur','Nashik','Aurangabad','Solapur','Amravati','Navi Mumbai','Thane','Kolhapur','Nanded','Latur','Akola','Chandrapur','Jalgaon','Ahmednagar','Sangli','Satara','Ratnagiri','Beed','Dharashiv','Wardha','Yavatmal','Parbhani','Jalna']),
    ('Manipur',               'MN', ['Imphal','Thoubal','Churachandpur','Ukhrul','Bishnupur']),
    ('Meghalaya',             'ML', ['Shillong','Tura','Jowai','Nongstoin']),
    ('Mizoram',               'MZ', ['Aizawl','Lunglei','Champhai','Serchhip','Kolasib']),
    ('Nagaland',              'NL', ['Kohima','Dimapur','Mokokchung','Tuensang','Zunheboto','Wokha']),
    ('Odisha',                'OD', ['Bhubaneswar','Cuttack','Rourkela','Berhampur','Sambalpur','Puri','Balasore','Baripada','Bhadrak','Angul','Jeypore','Koraput','Jharsuguda','Kendrapara']),
    ('Punjab',                'PB', ['Ludhiana','Amritsar','Jalandhar','Patiala','Bathinda','Mohali','Hoshiarpur','Moga','Firozpur','Sangrur','Barnala','Kapurthala','Fazilka','Gurdaspur','Pathankot','Nawanshahr']),
    ('Rajasthan',             'RJ', ['Jaipur','Jodhpur','Kota','Bikaner','Ajmer','Udaipur','Bhilwara','Alwar','Sikar','Sri Ganganagar','Pali','Tonk','Barmer','Dholpur','Sawai Madhopur','Churu','Jhunjhunu','Chittorgarh','Banswara','Dausa']),
    ('Sikkim',                'SK', ['Gangtok','Namchi','Gyalshing','Mangan']),
    ('Tamil Nadu',            'TN', ['Chennai','Coimbatore','Madurai','Tiruchirappalli','Salem','Tirunelveli','Erode','Vellore','Tiruppur','Nagercoil','Thanjavur','Dindigul','Kanchipuram','Cuddalore','Karur','Namakkal','Sivaganga','Virudhunagar','Krishnagiri','Ariyalur','Pudukkottai','Theni','Ramanathapuram','Nagapattinam']),
    ('Telangana',             'TG', ['Hyderabad','Warangal','Nizamabad','Khammam','Karimnagar','Ramagundam','Adilabad','Mahbubnagar','Nalgonda','Suryapet','Siddipet','Miryalaguda','Jagtial']),
    ('Tripura',               'TR', ['Agartala','Udaipur','Dharmanagar','Kailashahar','Belonia']),
    ('Uttar Pradesh',         'UP', ['Lucknow','Kanpur','Agra','Varanasi','Meerut','Prayagraj','Ghaziabad','Bareilly','Moradabad','Gorakhpur','Saharanpur','Firozabad','Shahjahanpur','Mathura','Rampur','Aligarh','Muzaffarnagar','Loni','Noida','Jhansi','Ayodhya','Basti','Sitapur','Hardoi','Unnao','Etawah','Mainpuri','Budaun','Bulandshahr','Amroha','Deoria','Ballia','Azamgarh','Jaunpur','Mirzapur','Sultanpur','Bahraich','Gonda','Pilibhit']),
    ('Uttarakhand',           'UK', ['Dehradun','Haridwar','Roorkee','Haldwani','Kashipur','Nainital','Almora','Pithoragarh','Rudrapur','Rishikesh']),
    ('West Bengal',           'WB', ['Kolkata','Howrah','Durgapur','Asansol','Siliguri','Bardhaman','Berhampore','Malda','Jalpaiguri','Cooch Behar','Kharagpur','Krishnanagar','Baharampur','Purulia','Bankura','Medinipur','Raiganj']),
    # Union Territories
    ('Andaman and Nicobar Islands',                    'AN', ['Port Blair']),
    ('Chandigarh',                                     'CH', ['Chandigarh']),
    ('Dadra and Nagar Haveli and Daman and Diu',       'DN', ['Daman','Silvassa','Diu']),
    ('Delhi',                                          'DL', ['New Delhi','Delhi','Dwarka','Rohini','Shahdara']),
    ('Jammu and Kashmir',                              'JK', ['Srinagar','Jammu','Sopore','Anantnag','Baramulla','Udhampur','Kathua']),
    ('Ladakh',                                         'LA', ['Leh','Kargil']),
    ('Lakshadweep',                                    'LD', ['Kavaratti']),
    ('Puducherry',                                     'PY', ['Puducherry','Karaikal','Mahe','Yanam']),
]


# ── Email Template Categories ──────────────────────────────────────────────────

EMAIL_CATEGORIES = [
    {'name': 'wish',         'display_name': 'Wishes',        'is_builtin': True, 'order': 1},
    {'name': 'reminder',     'display_name': 'Reminders',     'is_builtin': True, 'order': 2},
    {'name': 'notification', 'display_name': 'Notifications', 'is_builtin': True, 'order': 3},
    {'name': 'document',     'display_name': 'Documents',     'is_builtin': True, 'order': 4},
    {'name': 'recruitment',  'display_name': 'Recruitment',   'is_builtin': True, 'order': 5},
    {'name': 'onboarding',   'display_name': 'Onboarding',    'is_builtin': True, 'order': 6},
    {'name': 'hrms',         'display_name': 'HRMS',          'is_builtin': True, 'order': 7},
]


# ── Email Templates ────────────────────────────────────────────────────────────

EMAIL_TEMPLATES = [
    # ── Wishes ────────────────────────────────────────────────────────────────
    {
        'name': 'birthday',
        'display_name': 'Birthday Wish',
        'description': "Sent automatically on the employee's birthday.",
        'template_type': 'wish',
        'subject': 'Happy Birthday, {FNAME}!',
        'body': (
            '<p>Dear {FULL_NAME},</p>'
            '<p>On behalf of the entire <strong>Royal Staffing</strong> team, '
            'we wish you a very <strong>Happy Birthday</strong>! '
            'May this special day bring you joy, laughter, and all the happiness you deserve.</p>'
            '<p>Thank you for the wonderful contribution you make every day. '
            "Here's to another amazing year ahead!</p>"
            '<p>Warm regards,<br>HR Team<br>Royal Staffing Services</p>'
        ),
        'is_builtin': True,
        'available_variables': ['FNAME','LNAME','FULL_NAME','EMAIL','DEPARTMENT','DESIGNATION','COMPANY'],
    },
    {
        'name': 'work_anniversary',
        'display_name': 'Work Anniversary',
        'description': "Sent on the employee's date-of-joining anniversary.",
        'template_type': 'wish',
        'subject': 'Happy Work Anniversary, {FNAME}! {YEARS} Year(s) with Us',
        'body': (
            '<p>Dear {FULL_NAME},</p>'
            '<p>Today marks <strong>{YEARS} wonderful year(s)</strong> since you joined '
            '<strong>Royal Staffing Services</strong>!</p>'
            '<p>We deeply appreciate your dedication, hard work, and the positive impact you bring '
            'to the {DEPARTMENT} team every single day. '
            'You are a valued part of our family and we look forward to many more successful years together.</p>'
            '<p>Congratulations and thank you for being an integral part of our journey!</p>'
            '<p>Warm regards,<br>HR Team<br>Royal Staffing Services</p>'
        ),
        'is_builtin': True,
        'available_variables': ['FNAME','LNAME','FULL_NAME','EMAIL','DEPARTMENT','DESIGNATION','COMPANY','JOINING_DATE','YEARS'],
    },
    {
        'name': 'marriage_anniversary',
        'display_name': 'Marriage Anniversary',
        'description': "Sent on the employee's wedding anniversary.",
        'template_type': 'wish',
        'subject': 'Happy Anniversary, {FNAME}!',
        'body': (
            '<p>Dear {FULL_NAME},</p>'
            '<p>Wishing you and your partner a very <strong>Happy Wedding Anniversary</strong>!</p>'
            '<p>May your bond grow stronger with each passing year, '
            'and may your life together be filled with love, laughter, and endless happiness.</p>'
            '<p>Warm regards,<br>HR Team<br>Royal Staffing Services</p>'
        ),
        'is_builtin': True,
        'available_variables': ['FNAME','LNAME','FULL_NAME','EMAIL','COMPANY'],
    },
    {
        'name': 'onboarding',
        'display_name': 'Welcome / Onboarding',
        'description': 'Sent to new employees on their first day.',
        'template_type': 'wish',
        'subject': 'Welcome to Royal Staffing, {FNAME}!',
        'body': (
            '<p>Dear {FULL_NAME},</p>'
            '<p>We are absolutely thrilled to welcome you to <strong>Royal Staffing Services</strong>!</p>'
            '<p>Here are your details:</p>'
            '<ul>'
            '<li><strong>Employee ID:</strong> {EMPLOYEE_ID}</li>'
            '<li><strong>Department:</strong> {DEPARTMENT}</li>'
            '<li><strong>Designation:</strong> {DESIGNATION}</li>'
            '<li><strong>Date of Joining:</strong> {JOINING_DATE}</li>'
            '</ul>'
            '<p>Please reach out to your HR team if you need any assistance getting started. '
            'We look forward to having you on board and are excited about the contributions '
            'you will bring to our team.</p>'
            '<p>Warm regards,<br>HR Team<br>Royal Staffing Services</p>'
        ),
        'is_builtin': True,
        'available_variables': ['FNAME','LNAME','FULL_NAME','EMAIL','EMPLOYEE_ID','DEPARTMENT','DESIGNATION','JOINING_DATE','COMPANY'],
    },
    # ── Documents ─────────────────────────────────────────────────────────────
    {
        'name': 'payslip',
        'display_name': 'Pay Slip',
        'description': 'Notification email when a pay slip is generated.',
        'template_type': 'document',
        'subject': 'Your Pay Slip for {MONTH} {YEAR} — Royal Staffing',
        'body': (
            '<p>Dear {FULL_NAME},</p>'
            '<p>Please find your <strong>Pay Slip for {MONTH} {YEAR}</strong> attached to this email.</p>'
            '<p>If you have any queries regarding your salary, please contact the HR/Payroll team.</p>'
            '<p>Regards,<br>Payroll Team<br>Royal Staffing Services</p>'
        ),
        'is_builtin': True,
        'available_variables': ['FNAME','LNAME','FULL_NAME','EMAIL','EMPLOYEE_ID','MONTH','YEAR','COMPANY'],
    },
    # ── Reminders ─────────────────────────────────────────────────────────────
    {
        'name': 'confirmation_date',
        'display_name': 'Confirmation Date',
        'description': "Reminder sent when an employee's confirmation date is approaching.",
        'template_type': 'reminder',
        'subject': 'Reminder: Employee Confirmation — {FULL_NAME}',
        'body': (
            '<p>Dear {MANAGER_NAME},</p>'
            '<p>This is a reminder that <strong>{FULL_NAME}</strong> ({EMPLOYEE_ID}) '
            'is due for confirmation on <strong>{CONFIRMATION_DATE}</strong>.</p>'
            '<p>Please initiate the confirmation process at the earliest.</p>'
            '<p>Regards,<br>HR Team<br>Royal Staffing Services</p>'
        ),
        'is_builtin': True,
        'available_variables': ['FULL_NAME','EMPLOYEE_ID','DEPARTMENT','DESIGNATION','CONFIRMATION_DATE','MANAGER_NAME','COMPANY'],
    },
    {
        'name': 'date_of_joining',
        'display_name': 'Date of Joining',
        'description': 'Confirmation email sent to employee with joining details.',
        'template_type': 'reminder',
        'subject': 'Your Joining Details — Royal Staffing',
        'body': (
            '<p>Dear {FULL_NAME},</p>'
            '<p>We are pleased to confirm that you have been onboarded to <strong>Royal Staffing Services</strong> '
            'as <strong>{DESIGNATION}</strong> in the <strong>{DEPARTMENT}</strong> department, '
            'effective <strong>{JOINING_DATE}</strong>.</p>'
            '<p>Your Employee ID is <strong>{EMPLOYEE_ID}</strong>.</p>'
            '<p>Should you have any questions, please feel free to reach out to the HR team.</p>'
            '<p>Regards,<br>HR Team<br>Royal Staffing Services</p>'
        ),
        'is_builtin': True,
        'available_variables': ['FNAME','LNAME','FULL_NAME','EMAIL','EMPLOYEE_ID','DEPARTMENT','DESIGNATION','JOINING_DATE','COMPANY'],
    },
    {
        'name': 'date_of_retirement',
        'display_name': 'Date of Retirement',
        'description': 'Sent to the employee and HR when retirement date is approaching.',
        'template_type': 'reminder',
        'subject': 'Retirement Notice — {FULL_NAME}',
        'body': (
            '<p>Dear {FULL_NAME},</p>'
            '<p>This is to inform you that your retirement date is approaching on '
            '<strong>{RETIREMENT_DATE}</strong>.</p>'
            '<p>We sincerely thank you for your years of dedication and service to '
            '<strong>Royal Staffing Services</strong>. '
            'Your contributions have been invaluable to our organization.</p>'
            '<p>Our HR team will reach out to you shortly to complete the exit formalities.</p>'
            '<p>We wish you a very happy and fulfilling retirement!</p>'
            '<p>Warm regards,<br>HR Team<br>Royal Staffing Services</p>'
        ),
        'is_builtin': True,
        'available_variables': ['FNAME','LNAME','FULL_NAME','EMAIL','EMPLOYEE_ID','DEPARTMENT','DESIGNATION','JOINING_DATE','RETIREMENT_DATE','YEARS','COMPANY'],
    },
    # ── Recruitment / Onboarding ───────────────────────────────────────────────
    {
        'name': 'portal_invite',
        'display_name': 'Portal Login Invitation',
        'description': 'Sent to selected candidates with their portal login credentials.',
        'template_type': 'recruitment',
        'subject': 'Your Onboarding Portal Access — {company_name}',
        'body': (
            '<p>Dear {candidate_name},</p>\n\n'
            '<p>Congratulations! We are pleased to inform you that you have been selected for the position of '
            '<strong>{position}</strong> at <strong>{company_name}</strong>.</p>\n\n'
            '<p>Please use the following credentials to access your onboarding portal and complete your profile:</p>\n\n'
            '<table style="border-collapse:collapse;margin:16px 0;">\n'
            '  <tr>\n'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Portal URL</td>\n'
            '    <td style="padding:6px 12px;">{portal_url}</td>\n'
            '  </tr>\n'
            '  <tr>\n'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Login Email</td>\n'
            '    <td style="padding:6px 12px;">{login_email}</td>\n'
            '  </tr>\n'
            '  <tr>\n'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Temporary Password</td>\n'
            '    <td style="padding:6px 12px;font-family:monospace;letter-spacing:1px;">{temp_password}</td>\n'
            '  </tr>\n'
            '</table>\n\n'
            '<p>Once you log in, the onboarding wizard will guide you through filling '
            'in your personal, educational, and bank details and uploading the required '
            'documents. Please complete all steps as soon as possible so HR can process '
            'your joining formalities.</p>\n\n'
            '<p><strong>Please complete your profile at the earliest so HR can process your joining formalities.</strong></p>\n\n'
            '<p style="color:#888;font-size:13px;">If you did not expect this email, please ignore it or contact HR immediately.</p>\n\n'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_builtin': False,
        'available_variables': ['candidate_name','position','company_name','login_email','temp_password','portal_url'],
    },
    {
        'name': 'onboarding_approved',
        'display_name': 'Onboarding Approved — Welcome Email',
        'description': 'Sent to the employee after HR approves their onboarding submission.',
        'template_type': 'onboarding',
        'subject': 'Welcome to {company_name} — Onboarding Approved',
        'body': (
            '<p>Dear {employee_name},</p>\n\n'
            '<p>We are delighted to welcome you to <strong>{company_name}</strong>!</p>\n\n'
            '<p>Your onboarding has been reviewed and <strong>approved</strong> by HR. You are now an official member of our team.</p>\n\n'
            '<table style="border-collapse:collapse;margin:16px 0;">\n'
            '  <tr>\n'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Employee ID</td>\n'
            '    <td style="padding:6px 12px;font-family:monospace;">{employee_id}</td>\n'
            '  </tr>\n'
            '  <tr>\n'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Designation</td>\n'
            '    <td style="padding:6px 12px;">{designation}</td>\n'
            '  </tr>\n'
            '  <tr>\n'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Department</td>\n'
            '    <td style="padding:6px 12px;">{department}</td>\n'
            '  </tr>\n'
            '  <tr>\n'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Date of Joining</td>\n'
            '    <td style="padding:6px 12px;">{date_of_joining}</td>\n'
            '  </tr>\n'
            '</table>\n\n'
            '<p>As the next step, please log in to the portal and complete the '
            'assigned assessment(s). <strong>Full access to the employment portal — '
            'including your dashboard, payslips, and leave requests — will be unlocked '
            'once you have completed all assessments.</strong></p>\n\n'
            '<p style="background:#fef9c3;border-left:4px solid #eab308;padding:12px 16px;'
            'border-radius:4px;margin:16px 0;">'
            '&#9888;&nbsp; If you do not clear an assessment on the first attempt, '
            'you can retry it as many times as needed from the portal.</p>\n\n'
            '<p style="margin:24px 0;">\n'
            '  <a href="{portal_url}"\n'
            '     style="background:#4f46e5;color:#ffffff;padding:12px 28px;\n'
            '            border-radius:6px;text-decoration:none;font-weight:600;">\n'
            '    Go to Portal &amp; Complete Assessment\n'
            '  </a>\n'
            '</p>\n\n'
            '<p>If you have any questions, please reach out to the HR team.</p>\n\n'
            '<p>Welcome aboard!<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_builtin': False,
        'available_variables': ['employee_name','company_name','employee_id','designation','department','date_of_joining','portal_url','has_assessments','assessment_count'],
    },
    {
        'name': 'onboarding_rejected',
        'display_name': 'Onboarding Returned for Corrections',
        'description': 'Sent to the employee when HR sends the onboarding back for corrections.',
        'template_type': 'onboarding',
        'subject': 'Action Required: Please Update Your Onboarding Profile — {company_name}',
        'body': (
            '<p>Dear {employee_name},</p>\n\n'
            '<p>Thank you for completing your onboarding profile with <strong>{company_name}</strong>.</p>\n\n'
            '<p>After reviewing your submission, HR has requested some corrections before your profile can be approved. '
            'Please log back into the portal and address the points below:</p>\n\n'
            '<blockquote style="border-left:4px solid #e5e7eb;margin:16px 0;padding:12px 20px;'
            'background:#f9fafb;color:#374151;border-radius:4px;">\n'
            '  {remarks}\n'
            '</blockquote>\n\n'
            '<p>Once you have made the necessary updates, please re-submit your onboarding form so HR can process your joining formalities.</p>\n\n'
            '<p style="margin:24px 0;">\n'
            '  <a href="{portal_url}"\n'
            '     style="background:#4f46e5;color:#ffffff;padding:12px 28px;\n'
            '            border-radius:6px;text-decoration:none;font-weight:600;">\n'
            '    Return to Onboarding Portal\n'
            '  </a>\n'
            '</p>\n\n'
            '<p>If you have any questions, please contact HR directly.</p>\n\n'
            '<p>Regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_builtin': False,
        'available_variables': ['employee_name','company_name','remarks','portal_url'],
    },
    {
        'name': 'assessment_assigned',
        'display_name': 'Assessment Assigned',
        'description': 'Sent to a candidate when HR manually assigns a new assessment.',
        'template_type': 'onboarding',
        'subject': 'New Assessment Assigned — {company_name}',
        'body': (
            '<p>Dear {candidate_name},</p>'
            '<p>A new assessment has been assigned to you as part of your onboarding process at '
            '<strong>{company_name}</strong>.</p>'
            '<table style="border-collapse:collapse;margin:16px 0;">'
            '  <tr>'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Assessment</td>'
            '    <td style="padding:6px 12px;">{assessment_title}</td>'
            '  </tr>'
            '  <tr>'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Portal URL</td>'
            '    <td style="padding:6px 12px;">{portal_url}</td>'
            '  </tr>'
            '</table>'
            '<p>Please log in to your portal and complete this assessment at your earliest convenience. '
            'The onboarding wizard will become available once all assessments are completed.</p>'
            '<p><strong>Please complete this at the earliest so HR can process your joining formalities.</strong></p>'
            '<p style="color:#888;font-size:13px;">If you did not expect this email, please ignore it or contact HR immediately.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_builtin': True,
        'available_variables': ['candidate_name','assessment_title','company_name','portal_url'],
    },
    {
        'name': 'onboarding_submitted',
        'display_name': 'Onboarding Submitted (HR Notification)',
        'description': 'Sent to HR when a candidate submits the onboarding wizard for review.',
        'template_type': 'onboarding',
        'subject': 'Onboarding Submitted — {candidate_name} is ready for review',
        'body': (
            '<p>Dear {hr_name},</p>'
            '<p>A candidate has completed and submitted their onboarding wizard. '
            'Please log in to review and approve their details.</p>'
            '<table style="border-collapse:collapse;margin:16px 0;">'
            '  <tr>'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Candidate</td>'
            '    <td style="padding:6px 12px;">{candidate_name}</td>'
            '  </tr>'
            '  <tr>'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Email</td>'
            '    <td style="padding:6px 12px;">{candidate_email}</td>'
            '  </tr>'
            '</table>'
            '<p>Log in to the HR portal to review the submission and take action.</p>'
            '<p style="margin:20px 0;">'
            '  <a href="{portal_url}" '
            '     style="background:#1d4ed8;color:#fff;padding:10px 20px;border-radius:4px;'
            'text-decoration:none;font-weight:600;">Review Onboarding</a>'
            '</p>'
            '<p style="color:#888;font-size:13px;">This is an automated notification from the HRMS system.</p>'
            '<p>Regards,<br/><strong>HRMS — {company_name}</strong></p>'
        ),
        'is_builtin': True,
        'available_variables': ['hr_name','candidate_name','candidate_email','company_name','portal_url'],
    },
    {
        'name': 'birthday_wish',
        'display_name': 'Birthday Wish',
        'description': 'Sent automatically to an employee on their birthday at 9 AM.',
        'template_type': 'hrms',
        'subject': 'Happy Birthday, {employee_name}! \U0001f382',
        'body': (
            '<p>Dear {employee_name},</p>'
            '<p>On behalf of everyone at <strong>{company_name}</strong>, '
            'we wish you a very <strong>Happy Birthday!</strong> \U0001f389</p>'
            '<p>May this special day bring you joy, good health, and all the happiness '
            'you deserve. Your dedication and hard work make our team stronger every day, '
            'and we are grateful to have you with us.</p>'
            "<p>Here's to another wonderful year ahead!</p>"
            '<p style="margin-top:24px;">Warm regards,<br/>'
            '<strong>HR Team — {company_name}</strong></p>'
        ),
        'is_builtin': True,
        'available_variables': ['employee_name','company_name'],
    },
]


class Command(BaseCommand):
    help = 'Re-seeds states, cities, email template categories, email templates, and EmployeeCodeSettings'

    def handle(self, *args, **options):
        with transaction.atomic():
            self._seed_states_cities()
            self._seed_email_categories()
            self._seed_email_templates()
            self._seed_employee_code_settings()
        self.stdout.write(self.style.SUCCESS('\nAll reference data seeded successfully.'))

    # ── States & Cities ────────────────────────────────────────────────────────

    def _seed_states_cities(self):
        from apps.branch.models import State, City
        state_count = city_count = 0
        for state_name, code, cities in STATES_AND_CITIES:
            state, created = State.objects.get_or_create(
                name=state_name,
                defaults={'code': code, 'is_active': True},
            )
            if created:
                state_count += 1
            for city_name in cities:
                _, c_created = City.objects.get_or_create(
                    name=city_name, state=state,
                    defaults={'is_active': True},
                )
                if c_created:
                    city_count += 1
        self.stdout.write(f'  States:  {state_count} created (total {State.objects.count()})')
        self.stdout.write(f'  Cities:  {city_count} created (total {City.objects.count()})')

    # ── Email Template Categories ──────────────────────────────────────────────

    def _seed_email_categories(self):
        from apps.accounts.models import EmailTemplateCategory
        count = 0
        for cat in EMAIL_CATEGORIES:
            _, created = EmailTemplateCategory.objects.get_or_create(
                name=cat['name'],
                defaults={k: v for k, v in cat.items() if k != 'name'},
            )
            if created:
                count += 1
        self.stdout.write(f'  Email categories:  {count} created (total {EmailTemplateCategory.objects.count()})')

    # ── Email Templates ────────────────────────────────────────────────────────

    def _seed_email_templates(self):
        from apps.accounts.models import EmailTemplate
        count = 0
        for tpl in EMAIL_TEMPLATES:
            _, created = EmailTemplate.objects.get_or_create(
                name=tpl['name'],
                defaults={**{k: v for k, v in tpl.items() if k != 'name'}, 'is_active': True},
            )
            if created:
                count += 1
        self.stdout.write(f'  Email templates:   {count} created (total {EmailTemplate.objects.count()})')

    # ── EmployeeCodeSettings ───────────────────────────────────────────────────

    def _seed_employee_code_settings(self):
        from apps.accounts.models import EmployeeCodeSettings
        _, created = EmployeeCodeSettings.objects.get_or_create(
            id=1,
            defaults={'prefix': 'RSS', 'padding': 5, 'next_sequence': 1},
        )
        self.stdout.write(f'  EmployeeCodeSettings: {"created" if created else "already exists"}')
