from django.db import migrations

STATES_AND_CITIES = [
    # (state_name, state_code, [cities])
    ('Andhra Pradesh', 'AP', [
        'Visakhapatnam', 'Vijayawada', 'Guntur', 'Nellore', 'Kurnool',
        'Tirupati', 'Kadapa', 'Rajahmundry', 'Anantapur', 'Chittoor',
        'Eluru', 'Ongole', 'Srikakulam', 'Vizianagaram', 'Machilipatnam',
        'Chirala', 'Adoni', 'Tenali', 'Proddatur', 'Nandyal', 'Hindupur',
    ]),
    ('Arunachal Pradesh', 'AR', ['Itanagar', 'Naharlagun', 'Pasighat', 'Tawang', 'Ziro', 'Bomdila']),
    ('Assam', 'AS', [
        'Guwahati', 'Dibrugarh', 'Silchar', 'Jorhat', 'Tezpur',
        'Nagaon', 'Tinsukia', 'Karimganj', 'Sivasagar', 'Goalpara',
        'Barpeta', 'Dhubri', 'Diphu', 'North Lakhimpur',
    ]),
    ('Bihar', 'BR', [
        'Patna', 'Gaya', 'Bhagalpur', 'Muzaffarpur',
        'Purnia', 'Arrah', 'Darbhanga', 'Bihar Sharif',
        'Katihar', 'Munger', 'Chapra', 'Begusarai', 'Bettiah',
        'Motihari', 'Siwan', 'Sasaram', 'Hajipur', 'Nawada',
        'Samastipur', 'Gopalganj',
    ]),
    ('Chhattisgarh', 'CG', [
        'Raipur', 'Bhilai', 'Durg', 'Bilaspur', 'Korba',
        'Rajnandgaon', 'Jagdalpur', 'Ambikapur', 'Dhamtari', 'Raigarh',
    ]),
    ('Goa', 'GA', ['Panaji', 'Margao', 'Vasco da Gama', 'Mapusa', 'Ponda', 'Bicholim']),
    ('Gujarat', 'GJ', [
        'Ahmedabad', 'Surat', 'Vadodara', 'Rajkot',
        'Bhavnagar', 'Jamnagar', 'Junagadh', 'Gandhinagar',
        'Anand', 'Nadiad', 'Morbi', 'Mehsana', 'Bharuch',
        'Navsari', 'Valsad', 'Porbandar', 'Godhra', 'Patan', 'Surendranagar',
    ]),
    ('Haryana', 'HR', [
        'Faridabad', 'Gurgaon', 'Hisar', 'Rohtak',
        'Panipat', 'Karnal', 'Ambala', 'Yamunanagar',
        'Sonipat', 'Kurukshetra', 'Bhiwani', 'Sirsa',
        'Jind', 'Kaithal', 'Rewari', 'Palwal', 'Fatehabad',
    ]),
    ('Himachal Pradesh', 'HP', [
        'Shimla', 'Dharamsala', 'Manali', 'Mandi', 'Solan',
        'Kullu', 'Una', 'Bilaspur', 'Hamirpur', 'Chamba', 'Nahan',
    ]),
    ('Jharkhand', 'JH', [
        'Ranchi', 'Jamshedpur', 'Dhanbad', 'Bokaro', 'Deoghar',
        'Hazaribagh', 'Giridih', 'Ramgarh', 'Dumka', 'Chaibasa', 'Phusro',
    ]),
    ('Karnataka', 'KA', [
        'Bengaluru', 'Mysuru', 'Mangaluru', 'Hubli', 'Belagavi',
        'Shivamogga', 'Davanagere', 'Ballari', 'Kalaburagi', 'Tumakuru',
        'Chikkamagaluru', 'Udupi', 'Chitradurga', 'Bidar', 'Hassan',
        'Kolar', 'Mandya', 'Raichur', 'Bagalkot', 'Koppal', 'Haveri',
        'Vijayapura', 'Gadag',
    ]),
    ('Kerala', 'KL', [
        'Thiruvananthapuram', 'Kochi', 'Kozhikode',
        'Thrissur', 'Kollam', 'Kannur', 'Alappuzha',
        'Palakkad', 'Malappuram', 'Kottayam', 'Pathanamthitta',
        'Idukki', 'Kalpetta', 'Kasaragod',
    ]),
    ('Madhya Pradesh', 'MP', [
        'Bhopal', 'Indore', 'Jabalpur', 'Gwalior',
        'Ujjain', 'Ratlam', 'Sagar', 'Satna',
        'Rewa', 'Dewas', 'Khandwa', 'Chhindwara', 'Vidisha',
        'Guna', 'Shivpuri', 'Damoh', 'Singrauli', 'Burhanpur',
    ]),
    ('Maharashtra', 'MH', [
        'Mumbai', 'Pune', 'Nagpur', 'Nashik', 'Aurangabad',
        'Solapur', 'Amravati', 'Navi Mumbai', 'Thane',
        'Kolhapur', 'Nanded', 'Latur', 'Akola', 'Chandrapur',
        'Jalgaon', 'Ahmednagar', 'Sangli', 'Satara', 'Ratnagiri',
        'Beed', 'Dharashiv', 'Wardha', 'Yavatmal', 'Parbhani', 'Jalna',
    ]),
    ('Manipur', 'MN', ['Imphal', 'Thoubal', 'Churachandpur', 'Ukhrul', 'Bishnupur']),
    ('Meghalaya', 'ML', ['Shillong', 'Tura', 'Jowai', 'Nongstoin']),
    ('Mizoram', 'MZ', ['Aizawl', 'Lunglei', 'Champhai', 'Serchhip', 'Kolasib']),
    ('Nagaland', 'NL', ['Kohima', 'Dimapur', 'Mokokchung', 'Tuensang', 'Zunheboto', 'Wokha']),
    ('Odisha', 'OD', [
        'Bhubaneswar', 'Cuttack', 'Rourkela', 'Berhampur', 'Sambalpur', 'Puri',
        'Balasore', 'Baripada', 'Bhadrak', 'Angul', 'Jeypore', 'Koraput',
        'Jharsuguda', 'Kendrapara',
    ]),
    ('Punjab', 'PB', [
        'Ludhiana', 'Amritsar', 'Jalandhar', 'Patiala', 'Bathinda', 'Mohali',
        'Hoshiarpur', 'Moga', 'Firozpur', 'Sangrur', 'Barnala', 'Kapurthala',
        'Fazilka', 'Gurdaspur', 'Pathankot', 'Nawanshahr',
    ]),
    ('Rajasthan', 'RJ', [
        'Jaipur', 'Jodhpur', 'Kota', 'Bikaner',
        'Ajmer', 'Udaipur', 'Bhilwara', 'Alwar', 'Sikar',
        'Sri Ganganagar', 'Pali', 'Tonk', 'Barmer', 'Dholpur',
        'Sawai Madhopur', 'Churu', 'Jhunjhunu', 'Chittorgarh', 'Banswara', 'Dausa',
    ]),
    ('Sikkim', 'SK', ['Gangtok', 'Namchi', 'Gyalshing', 'Mangan']),
    ('Tamil Nadu', 'TN', [
        'Chennai', 'Coimbatore', 'Madurai', 'Tiruchirappalli', 'Salem',
        'Tirunelveli', 'Erode', 'Vellore', 'Tiruppur', 'Nagercoil',
        'Thanjavur', 'Dindigul', 'Kanchipuram', 'Cuddalore', 'Karur',
        'Namakkal', 'Sivaganga', 'Virudhunagar', 'Krishnagiri', 'Ariyalur',
        'Pudukkottai', 'Theni', 'Ramanathapuram', 'Nagapattinam',
    ]),
    ('Telangana', 'TG', [
        'Hyderabad', 'Warangal', 'Nizamabad', 'Khammam', 'Karimnagar', 'Ramagundam',
        'Adilabad', 'Mahbubnagar', 'Nalgonda', 'Suryapet', 'Siddipet',
        'Miryalaguda', 'Jagtial',
    ]),
    ('Tripura', 'TR', ['Agartala', 'Udaipur', 'Dharmanagar', 'Kailashahar', 'Belonia']),
    ('Uttar Pradesh', 'UP', [
        'Lucknow', 'Kanpur', 'Agra', 'Varanasi', 'Meerut', 'Prayagraj',
        'Ghaziabad', 'Bareilly', 'Moradabad', 'Gorakhpur', 'Saharanpur',
        'Firozabad', 'Shahjahanpur', 'Mathura', 'Rampur', 'Aligarh',
        'Muzaffarnagar', 'Loni', 'Noida', 'Jhansi', 'Ayodhya', 'Basti',
        'Sitapur', 'Hardoi', 'Unnao', 'Etawah', 'Mainpuri', 'Budaun',
        'Bulandshahr', 'Amroha', 'Deoria', 'Ballia', 'Azamgarh', 'Jaunpur',
        'Mirzapur', 'Sultanpur', 'Bahraich', 'Gonda', 'Pilibhit',
    ]),
    ('Uttarakhand', 'UK', [
        'Dehradun', 'Haridwar', 'Roorkee', 'Haldwani', 'Kashipur',
        'Nainital', 'Almora', 'Pithoragarh', 'Rudrapur', 'Rishikesh',
    ]),
    ('West Bengal', 'WB', [
        'Kolkata', 'Howrah', 'Durgapur', 'Asansol',
        'Siliguri', 'Bardhaman', 'Berhampore', 'Malda',
        'Jalpaiguri', 'Cooch Behar', 'Kharagpur', 'Krishnanagar',
        'Baharampur', 'Purulia', 'Bankura', 'Medinipur', 'Raiganj',
    ]),
    # Union Territories
    ('Andaman and Nicobar Islands', 'AN', ['Port Blair']),
    ('Chandigarh', 'CH', ['Chandigarh']),
    ('Dadra and Nagar Haveli and Daman and Diu', 'DN', ['Daman', 'Silvassa', 'Diu']),
    ('Delhi', 'DL', ['New Delhi', 'Delhi', 'Dwarka', 'Rohini', 'Shahdara']),
    ('Jammu and Kashmir', 'JK', ['Srinagar', 'Jammu', 'Sopore', 'Anantnag', 'Baramulla', 'Udhampur', 'Kathua']),
    ('Ladakh', 'LA', ['Leh', 'Kargil']),
    ('Lakshadweep', 'LD', ['Kavaratti']),
    ('Puducherry', 'PY', ['Puducherry', 'Karaikal', 'Mahe', 'Yanam']),
]


def seed_states_cities(apps, schema_editor):
    State = apps.get_model('branch', 'State')
    City = apps.get_model('branch', 'City')

    for state_name, state_code, cities in STATES_AND_CITIES:
        state, _ = State.objects.get_or_create(
            name=state_name,
            defaults={'code': state_code, 'is_active': True},
        )
        for city_name in cities:
            City.objects.get_or_create(
                name=city_name,
                state=state,
                defaults={'is_active': True},
            )


def remove_states_cities(apps, schema_editor):
    State = apps.get_model('branch', 'State')
    State.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('branch', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_states_cities, remove_states_cities),
    ]
