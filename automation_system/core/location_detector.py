"""
Location Detector for Indian Government & Private Recruitment
Accurately resolves specific Job Location (City, District, State) from:
- Organization Name
- Post Name
- Notification / Article URL Slug
- Scraped text / table snippet
- Central organization patterns
"""

import re
from urllib.parse import urlparse

# ==============================================================================
# 1. INSTITUTIONS & SPECIAL BOARDS WITH SPECIFIC HEADQUARTERS / CITIES
# ==============================================================================
SPECIAL_INSTITUTES = [
    # IITs
    (r"\biit\s*kanpur\b", "Kanpur, Uttar Pradesh"),
    (r"\biit\s*madras\b", "Chennai, Tamil Nadu"),
    (r"\biit\s*bombay\b", "Mumbai, Maharashtra"),
    (r"\biit\s*delhi\b", "New Delhi"),
    (r"\biit\s*kharagpur\b", "Kharagpur, West Bengal"),
    (r"\biit\s*roorkee\b", "Roorkee, Uttarakhand"),
    (r"\biit\s*guwahati\b", "Guwahati, Assam"),
    (r"\biit\s*hyderabad\b", "Hyderabad, Telangana"),
    (r"\biit\s*(?:bhu|varanasi)\b", "Varanasi, Uttar Pradesh"),
    (r"\biit\s*indore\b", "Indore, Madhya Pradesh"),
    (r"\biit\s*patna\b", "Patna, Bihar"),
    (r"\biit\s*gandhinagar\b", "Gandhinagar, Gujarat"),
    (r"\biit\s*ropar\b", "Rupnagar, Punjab"),
    (r"\biit\s*mandi\b", "Mandi, Himachal Pradesh"),
    (r"\biit\s*jodhpur\b", "Jodhpur, Rajasthan"),
    (r"\biit\s*tirupati\b", "Tirupati, Andhra Pradesh"),
    (r"\biit\s*palakkad\b", "Palakkad, Kerala"),
    (r"\biit\s*dharwad\b", "Dharwad, Karnataka"),
    (r"\biit\s*bhilai\b", "Bhilai, Chhattisgarh"),
    (r"\biit\s*goa\b", "Goa"),
    (r"\biit\s*jammu\b", "Jammu, J&K"),

    # IIMs
    (r"\biim\s*ahmedabad\b", "Ahmedabad, Gujarat"),
    (r"\biim\s*bangalore\b", "Bengaluru, Karnataka"),
    (r"\biim\s*calcutta\b", "Kolkata, West Bengal"),
    (r"\biim\s*lucknow\b", "Lucknow, Uttar Pradesh"),
    (r"\biim\s*indore\b", "Indore, Madhya Pradesh"),
    (r"\biim\s*kozhikode\b", "Kozhikode, Kerala"),
    (r"\biim\s*shillong\b", "Shillong, Meghalaya"),
    (r"\biim\s*rohtak\b", "Rohtak, Haryana"),
    (r"\biim\s*ranchi\b", "Ranchi, Jharkhand"),
    (r"\biim\s*raipur\b", "Raipur, Chhattisgarh"),
    (r"\biim\s*tiruchirappalli\b", "Tiruchirappalli, Tamil Nadu"),
    (r"\biim\s*kashipur\b", "Kashipur, Uttarakhand"),
    (r"\biim\s*udaipur\b", "Udaipur, Rajasthan"),
    (r"\biim\s*nagpur\b", "Nagpur, Maharashtra"),
    (r"\biim\s*visakhapatnam\b", "Visakhapatnam, Andhra Pradesh"),
    (r"\biim\s*bodh\s*gaya\b", "Bodh Gaya, Bihar"),
    (r"\biim\s*amritsar\b", "Amritsar, Punjab"),
    (r"\biim\s*sambalpur\b", "Sambalpur, Odisha"),
    (r"\biim\s*sirmaur\b", "Sirmaur, Himachal Pradesh"),
    (r"\biim\s*jammu\b", "Jammu, J&K"),

    # AIIMS
    (r"\baiims\s*new\s*delhi\b", "New Delhi"),
    (r"\baiims\s*bhopal\b", "Bhopal, Madhya Pradesh"),
    (r"\baiims\s*bhubaneswar\b", "Bhubaneswar, Odisha"),
    (r"\baiims\s*jodhpur\b", "Jodhpur, Rajasthan"),
    (r"\baiims\s*patna\b", "Patna, Bihar"),
    (r"\baiims\s*raipur\b", "Raipur, Chhattisgarh"),
    (r"\baiims\s*rishikesh\b", "Rishikesh, Uttarakhand"),
    (r"\baiims\s*nagpur\b", "Nagpur, Maharashtra"),
    (r"\baiims\s*mangalagiri\b", "Mangalagiri, Andhra Pradesh"),
    (r"\baiims\s*bibinagar\b", "Bibinagar, Telangana"),
    (r"\baiims\s*kalyani\b", "Kalyani, West Bengal"),
    (r"\baiims\s*deoghar\b", "Deoghar, Jharkhand"),
    (r"\baiims\s*gorakhpur\b", "Gorakhpur, Uttar Pradesh"),
    (r"\baiims\s*rae\s*bareli\b", "Rae Bareli, Uttar Pradesh"),
    (r"\baiims\s*bathinda\b", "Bathinda, Punjab"),
    (r"\baiims\s*bilaspur\b", "Bilaspur, Himachal Pradesh"),
    (r"\baiims\s*guwahati\b", "Guwahati, Assam"),
    (r"\baiims\s*rajkot\b", "Rajkot, Gujarat"),
    (r"\baiims\s*jammu\b", "Jammu, J&K"),

    # Ports, Academies, Institutes
    (r"\bcochin\s*port\b", "Kochi / Cochin, Kerala"),
    (r"\bmumbai\s*port\b", "Mumbai, Maharashtra"),
    (r"\bchennai\s*port\b", "Chennai, Tamil Nadu"),
    (r"\bkamarajar\s*port\b", "Chennai, Tamil Nadu"),
    (r"\bv\.?o\.?\s*chidambaranar\s*port\b", "Thoothukudi, Tamil Nadu"),
    (r"\bvisakhapatnam\s*port\b", "Visakhapatnam, Andhra Pradesh"),
    (r"\bparadip\s*port\b", "Paradip, Odisha"),
    (r"\bkandla\s*port|deendayal\s*port\b", "Kandla, Gujarat"),
    (r"\bjawaharlal\s*nehru\s*port|jnpt\b", "Navi Mumbai, Maharashtra"),
    (r"\bmormugao\s*port\b", "Goa"),
    (r"\bnew\s*mangalore\s*port\b", "Mangaluru, Karnataka"),
    (r"\bsyama\s*prasad\s*mookerjee\s*port|kolkata\s*port\b", "Kolkata, West Bengal"),
    (r"\bnational\s*communications\s*academy\b|\bnca-?f\b", "Vadodara, Gujarat"),
    (r"\bcentral\s*silk\s*board\b", "Bengaluru, Karnataka / Pan India"),
    (r"\bc-?dac\b", "Pune, Maharashtra / Multiple Locations"),
    (r"\bnid\s*madhya\s*pradesh\b", "Bhopal, Madhya Pradesh"),
    (r"\bnid\s*andhra\s*pradesh\b", "Vijayawada, Andhra Pradesh"),
    (r"\bnid\s*assam\b", "Jorhat, Assam"),
    (r"\bnid\s*haryana\b", "Kurukshetra, Haryana"),
    (r"\bnid\s*ahmedabad\b", "Ahmedabad, Gujarat"),

    # Renowned Universities & Institutes
    (r"\bkalyani\s*university\b", "Kalyani, West Bengal"),
    (r"\bdoon\s*university\b", "Dehradun, Uttarakhand"),
    (r"\biiest\s*shibpur\b|\bshibpur\b", "Howrah, West Bengal"),
    (r"\byoung\s*india\s*skills\s*university\b|\byisu\b", "Hyderabad, Telangana"),
    (r"\bindia\s*optel\b|\biol\b", "Dehradun, Uttarakhand"),
    (r"\bicgeb\b", "New Delhi"),
    (r"\badvanced\s*systems\s*laboratory\b|\bdrdo\s*asl\b", "Hyderabad, Telangana"),
    (r"\bdrdo\s*drdl\b|\bdefence\s*research\s*&\s*development\s*laboratory\b", "Hyderabad, Telangana"),
    (r"\bdrdo\s*rci\b|\bresearch\s*centre\s*imarat\b", "Hyderabad, Telangana"),
    (r"\bdrdo\s*ade\b", "Bengaluru, Karnataka"),
    (r"\bdrdo\s*irde\b", "Dehradun, Uttarakhand"),
    (r"\bdrdo\s*vrde\b", "Ahmednagar, Maharashtra"),
    (r"\bdrdo\s*pxe\b", "Balasore, Odisha"),
    (r"\bisro\s*vssc\b", "Thiruvananthapuram, Kerala"),
    (r"\bisro\s*sdsc\b|\bsriharikota\b|\bshar\b", "Sriharikota, Andhra Pradesh"),
    (r"\bisro\s*ursc\b|\bisro\s*isac\b", "Bengaluru, Karnataka"),
    (r"\bisro\s*nrsc\b", "Hyderabad, Telangana"),
    (r"\bbarc\b|\bbhabha\s*atomic\b", "Mumbai, Maharashtra"),
    (r"\bigcar\b", "Kalpakkam, Tamil Nadu"),
    (r"\brrcat\b", "Indore, Madhya Pradesh"),
    (r"\bnfc\b|\bnuclear\s*fuel\s*complex\b", "Hyderabad, Telangana"),
    (r"\becil\b|\belectronics\s*corporation\s*of\s*india\b", "Hyderabad, Telangana"),
    (r"\bbdl\b|\bbharat\s*dynamics\b", "Hyderabad, Telangana"),
]

# ==============================================================================
# 2. STATE & CITY DETECTION RULES (IN ORDER OF SPECIFICITY)
# ==============================================================================
STATE_CITY_RULES = [
    # Telangana
    (
        r"\b(?:telangana|hyderabad|secunderabad|warangal|nizamabad|karimnagar|khammam|ramagundam|mahbubnagar|nalgonda|adilabad|suryapet|miryalaguda|siddipet|mancherial|tspsc|tgpsc|tsnpdcl|tssspdcl|tsrtc|singareni|sccl)\b",
        "Telangana",
        [
            ("hyderabad", "Hyderabad, Telangana"),
            ("secunderabad", "Secunderabad, Telangana"),
            ("warangal", "Warangal, Telangana"),
            ("nizamabad", "Nizamabad, Telangana"),
            ("karimnagar", "Karimnagar, Telangana"),
            ("khammam", "Khammam, Telangana"),
            ("ramagundam", "Ramagundam, Telangana"),
            ("mahbubnagar", "Mahbubnagar, Mahabubnagar, Telangana"),
            ("nalgonda", "Nalgonda, Telangana"),
            ("adilabad", "Adilabad, Telangana"),
            ("siddipet", "Siddipet, Telangana"),
            ("singareni", "Kothagudem / Telangana"),
        ]
    ),
    # Andhra Pradesh
    (
        r"\b(?:andhra\s*pradesh|amaravati|visakhapatnam|vizag|vijayawada|guntur|nellore|kurnool|tirupati|kakinada|rajahmundry|kadapa|anantapur|eluru|ongole|srikakulam|chittoor|machilipatnam|appsc|apspdcl|apepdcl|apcpdcl|apsrtc)\b",
        "Andhra Pradesh",
        [
            ("visakhapatnam", "Visakhapatnam, Andhra Pradesh"),
            ("vizag", "Visakhapatnam, Andhra Pradesh"),
            ("vijayawada", "Vijayawada, Andhra Pradesh"),
            ("guntur", "Guntur, Andhra Pradesh"),
            ("amaravati", "Amaravati, Andhra Pradesh"),
            ("nellore", "Nellore, Andhra Pradesh"),
            ("kurnool", "Kurnool, Andhra Pradesh"),
            ("tirupati", "Tirupati, Andhra Pradesh"),
            ("kakinada", "Kakinada, Andhra Pradesh"),
            ("rajahmundry", "Rajahmundry, Andhra Pradesh"),
            ("kadapa", "Kadapa, Andhra Pradesh"),
            ("anantapur", "Anantapur, Andhra Pradesh"),
            ("srikakulam", "Srikakulam, Andhra Pradesh"),
            ("chittoor", "Chittoor, Andhra Pradesh"),
        ]
    ),
    # Tamil Nadu
    (
        r"\b(?:tamil\s*nadu|tamilnadu|chennai|madras|coimbatore|madurai|tiruchirappalli|trichy|salem|tirunelveli|tiruppur|erode|vellore|thoothukudi|dindigul|thanjavur|ranipet|sivakasi|karur|udhagamandalam|ooty|hosur|nagercoil|kanchipuram|krishnagiri|cuddalore|tiruvannamalai|tnpsc|tnusrb|mrb\s*tamil)\b",
        "Tamil Nadu",
        [
            ("chennai", "Chennai, Tamil Nadu"),
            ("madras", "Chennai, Tamil Nadu"),
            ("coimbatore", "Coimbatore, Tamil Nadu"),
            ("madurai", "Madurai, Tamil Nadu"),
            ("tiruchirappalli", "Tiruchirappalli, Tamil Nadu"),
            ("trichy", "Tiruchirappalli, Tamil Nadu"),
            ("salem", "Salem, Tamil Nadu"),
            ("krishnagiri", "Krishnagiri, Tamil Nadu"),
            ("vellore", "Vellore, Tamil Nadu"),
            ("thoothukudi", "Thoothukudi, Tamil Nadu"),
            ("tirunelveli", "Tirunelveli, Tamil Nadu"),
            ("tiruppur", "Tiruppur, Tamil Nadu"),
            ("erode", "Erode, Tamil Nadu"),
            ("kanchipuram", "Kanchipuram, Tamil Nadu"),
        ]
    ),
    # Karnataka
    (
        r"\b(?:karnataka|bengaluru|bangalore|mysuru|mysore|hubballi|dharwad|mangaluru|mangalore|belagavi|belgaum|kalaburagi|gulbarga|davanagere|ballari|bellary|vijayapura|bijapur|shivamogga|shimoga|tumakuru|tumkur|raichur|bidar|hospet|gadag|udupi|kolar|kpsc|ksrtc|kptcl|bescom)\b",
        "Karnataka",
        [
            ("bengaluru", "Bengaluru, Karnataka"),
            ("bangalore", "Bengaluru, Karnataka"),
            ("mysuru", "Mysuru, Karnataka"),
            ("mysore", "Mysore, Karnataka"),
            ("mangaluru", "Mangaluru, Karnataka"),
            ("mangalore", "Mangalore, Karnataka"),
            ("hubballi", "Hubballi, Karnataka"),
            ("dharwad", "Dharwad, Karnataka"),
            ("belagavi", "Belagavi, Karnataka"),
            ("belgaum", "Belgaum, Karnataka"),
            ("kalaburagi", "Kalaburagi, Karnataka"),
            ("udupi", "Udupi, Karnataka"),
        ]
    ),
    # Maharashtra
    (
        r"\b(?:maharashtra|mumbai|bombay|pune|nagpur|thane|nashik|kalyan|dombivli|vasai|virar|aurangabad|chhatrapati\s*sambhajinagar|navi\s*mumbai|solapur|mira-?bhayandar|bhiwandi|amravati|nanded|kolhapur|akola|ulhasnagar|sangli|malegaon|jalgaon|latur|dhule|ahmednagar|chandrapur|parbhani|ichalkaranji|jalna|panvel|mpsc|maha\s*metro|mahagenco|mahadiscom)\b",
        "Maharashtra",
        [
            ("mumbai", "Mumbai, Maharashtra"),
            ("bombay", "Mumbai, Maharashtra"),
            ("pune", "Pune, Maharashtra"),
            ("nagpur", "Nagpur, Maharashtra"),
            ("thane", "Thane, Maharashtra"),
            ("nashik", "Nashik, Maharashtra"),
            ("navi mumbai", "Navi Mumbai, Maharashtra"),
            ("aurangabad", "Aurangabad / Sambhajinagar, Maharashtra"),
            ("sambhajinagar", "Chhatrapati Sambhajinagar, Maharashtra"),
            ("solapur", "Solapur, Maharashtra"),
            ("kolhapur", "Kolhapur, Maharashtra"),
            ("amravati", "Amravati, Maharashtra"),
            ("nanded", "Nanded, Maharashtra"),
        ]
    ),
    # Uttar Pradesh
    (
        r"\b(?:uttar\s*pradesh|\bup\b|lucknow|kanpur|ghaziabad|agra|meerut|varanasi|kashi|prayagraj|allahabad|bareilly|aligarh|moradabad|saharanpur|gorakhpur|noida|greater\s*noida|firozabad|jhansi|muzaffarnagar|mathura|ayodhya|faizabad|jalaun|mirzapur|raebareli|sitapur|uppsc|upsssc|uppcl|up\s*police)\b",
        "Uttar Pradesh",
        [
            ("lucknow", "Lucknow, Uttar Pradesh"),
            ("kanpur", "Kanpur, Uttar Pradesh"),
            ("ghaziabad", "Ghaziabad, Uttar Pradesh"),
            ("agra", "Agra, Uttar Pradesh"),
            ("meerut", "Meerut, Uttar Pradesh"),
            ("varanasi", "Varanasi, Uttar Pradesh"),
            ("kashi", "Varanasi, Uttar Pradesh"),
            ("prayagraj", "Prayagraj, Uttar Pradesh"),
            ("allahabad", "Prayagraj / Allahabad, Uttar Pradesh"),
            ("gorakhpur", "Gorakhpur, Uttar Pradesh"),
            ("noida", "Noida, Uttar Pradesh"),
            ("greater noida", "Greater Noida, Uttar Pradesh"),
            ("bareilly", "Bareilly, Uttar Pradesh"),
            ("aligarh", "Aligarh, Uttar Pradesh"),
            ("jhansi", "Jhansi, Uttar Pradesh"),
            ("jalaun", "Jalaun, Uttar Pradesh"),
            ("mathura", "Mathura, Uttar Pradesh"),
            ("ayodhya", "Ayodhya, Uttar Pradesh"),
            ("moradabad", "Moradabad, Uttar Pradesh"),
        ]
    ),
    # Madhya Pradesh
    (
        r"\b(?:madhya\s*pradesh|\bmp\b|indore|bhopal|jabalpur|gwalior|ujjain|sagar|dewas|satna|ratlam|rewa|katni|singrauli|burhanpur|khandwa|bhind|chhindwara|guna|shivpuri|vidisha|chhatarpur|damoh|mandsaur|khargone|neemuch|mppsc|mpesb|peb\s*mp)\b",
        "Madhya Pradesh",
        [
            ("indore", "Indore, Madhya Pradesh"),
            ("bhopal", "Bhopal, Madhya Pradesh"),
            ("jabalpur", "Jabalpur, Madhya Pradesh"),
            ("gwalior", "Gwalior, Madhya Pradesh"),
            ("ujjain", "Ujjain, Madhya Pradesh"),
            ("sagar", "Sagar, Madhya Pradesh"),
            ("satna", "Satna, Madhya Pradesh"),
            ("rewa", "Rewa, Madhya Pradesh"),
        ]
    ),
    # Gujarat
    (
        r"\b(?:gujarat|ahmedabad|surat|vadodara|baroda|rajkot|bhavnagar|jamnagar|junagadh|gandhinagar|gandhidham|anand|navsari|morbi|nadiad|surendranagar|bharuch|mehsana|bhuj|porbandar|valsad|vapi|gpsc|gsssb|gacl)\b",
        "Gujarat",
        [
            ("ahmedabad", "Ahmedabad, Gujarat"),
            ("surat", "Surat, Gujarat"),
            ("vadodara", "Vadodara, Gujarat"),
            ("baroda", "Vadodara, Gujarat"),
            ("rajkot", "Rajkot, Gujarat"),
            ("gandhinagar", "Gandhinagar, Gujarat"),
            ("bhavnagar", "Bhavnagar, Gujarat"),
            ("jamnagar", "Jamnagar, Gujarat"),
        ]
    ),
    # Rajasthan
    (
        r"\b(?:rajasthan|jaipur|jodhpur|kota|bikaner|ajmer|udaipur|bhilwara|alwar|bharatpur|sikar|pali|sri\s*ganganagar|kishangarh|baran|rpsc|rsmssb)\b",
        "Rajasthan",
        [
            ("jaipur", "Jaipur, Rajasthan"),
            ("jodhpur", "Jodhpur, Rajasthan"),
            ("kota", "Kota, Rajasthan"),
            ("bikaner", "Bikaner, Rajasthan"),
            ("ajmer", "Ajmer, Rajasthan"),
            ("udaipur", "Udaipur, Rajasthan"),
            ("alwar", "Alwar, Rajasthan"),
            ("sikar", "Sikar, Rajasthan"),
        ]
    ),
    # Bihar
    (
        r"\b(?:bihar|patna|gaya|bhagalpur|muzaffarpur|purnia|darbhanga|bihar\s*sharif|arrah|begusarai|katihar|munger|chhapra|danapur|bettiah|saharsa|sasaram|hajipur|dehri|siwan|motihari|nawada|bpsc|bssc)\b",
        "Bihar",
        [
            ("patna", "Patna, Bihar"),
            ("gaya", "Gaya, Bihar"),
            ("muzaffarpur", "Muzaffarpur, Bihar"),
            ("bhagalpur", "Bhagalpur, Bihar"),
            ("darbhanga", "Darbhanga, Bihar"),
            ("purnia", "Purnia, Bihar"),
        ]
    ),
    # West Bengal
    (
        r"\b(?:west\s*bengal|kolkata|calcutta|asansol|siliguri|durgapur|bardhaman|burdwan|malda|baharampur|habra|kharagpur|haldia|darjeeling|wbpsc|wbprb|wbcsc)\b",
        "West Bengal",
        [
            ("kolkata", "Kolkata, West Bengal"),
            ("calcutta", "Kolkata, West Bengal"),
            ("asansol", "Asansol, West Bengal"),
            ("siliguri", "Siliguri, West Bengal"),
            ("durgapur", "Durgapur, West Bengal"),
            ("kharagpur", "Kharagpur, West Bengal"),
            ("darjeeling", "Darjeeling, West Bengal"),
        ]
    ),
    # Odisha
    (
        r"\b(?:odisha|orissa|bhubaneswar|cuttack|rourkela|berhampur|sambalpur|puri|balasore|bhadrak|baripada|jharsuguda|opsc|ossc|osssc|optcl|ohpc)\b",
        "Odisha",
        [
            ("bhubaneswar", "Bhubaneswar, Odisha"),
            ("cuttack", "Cuttack, Odisha"),
            ("rourkela", "Rourkela, Odisha"),
            ("berhampur", "Berhampur, Odisha"),
            ("sambalpur", "Sambalpur, Odisha"),
            ("puri", "Puri, Odisha"),
        ]
    ),
    # Kerala
    (
        r"\b(?:kerala|thiruvananthapuram|trivandrum|kochi|cochin|kozhikode|calicut|kollam|thrissur|kannur|alappuzha|palakkad|kottayam|malappuram|kasargod|kerala\s*psc)\b",
        "Kerala",
        [
            ("thiruvananthapuram", "Thiruvananthapuram, Kerala"),
            ("trivandrum", "Thiruvananthapuram, Kerala"),
            ("kochi", "Kochi / Cochin, Kerala"),
            ("cochin", "Kochi / Cochin, Kerala"),
            ("kozhikode", "Kozhikode, Kerala"),
            ("calicut", "Kozhikode, Kerala"),
            ("thrissur", "Thrissur, Kerala"),
            ("kollam", "Kollam, Kerala"),
            ("kannur", "Kannur, Kerala"),
            ("palakkad", "Palakkad, Kerala"),
        ]
    ),
    # Punjab
    (
        r"\b(?:punjab|ludhiana|amritsar|jalandhar|patiala|bathinda|mohali|hoshiarpur|pathankot|ppsc|psssb)\b",
        "Punjab",
        [
            ("amritsar", "Amritsar, Punjab"),
            ("ludhiana", "Ludhiana, Punjab"),
            ("jalandhar", "Jalandhar, Punjab"),
            ("patiala", "Patiala, Punjab"),
            ("bathinda", "Bathinda, Punjab"),
            ("mohali", "Mohali / SAS Nagar, Punjab"),
        ]
    ),
    # Haryana
    (
        r"\b(?:haryana|faridabad|gurugram|gurgaon|panipat|ambala|yamunanagar|rohtak|hisar|karnal|sonipat|panchkula|hssc|hpsc)\b",
        "Haryana",
        [
            ("gurugram", "Gurugram, Haryana"),
            ("gurgaon", "Gurugram / Gurgaon, Haryana"),
            ("faridabad", "Faridabad, Haryana"),
            ("panipat", "Panipat, Haryana"),
            ("ambala", "Ambala, Haryana"),
            ("rohtak", "Rohtak, Haryana"),
            ("hisar", "Hisar, Haryana"),
            ("panchkula", "Panchkula, Haryana"),
        ]
    ),
    # Assam
    (
        r"\b(?:assam|guwahati|silchar|dibrugarh|jorhat|nagaon|tinsukia|tezpur|apsc)\b",
        "Assam",
        [
            ("guwahati", "Guwahati, Assam"),
            ("silchar", "Silchar, Assam"),
            ("dibrugarh", "Dibrugarh, Assam"),
            ("jorhat", "Jorhat, Assam"),
            ("tezpur", "Tezpur, Assam"),
        ]
    ),
    # Jharkhand
    (
        r"\b(?:jharkhand|ranchi|jamshedpur|dhanbad|bokaro|deoghar|hazaribagh|jpsc|jssc)\b",
        "Jharkhand",
        [
            ("ranchi", "Ranchi, Jharkhand"),
            ("jamshedpur", "Jamshedpur, Jharkhand"),
            ("dhanbad", "Dhanbad, Jharkhand"),
            ("bokaro", "Bokaro, Jharkhand"),
            ("deoghar", "Deoghar, Jharkhand"),
        ]
    ),
    # Chhattisgarh
    (
        r"\b(?:chhattisgarh|raipur|bhilai|bilaspur|korba|rajnandgaon|jagdalpur|cgpsc)\b",
        "Chhattisgarh",
        [
            ("raipur", "Raipur, Chhattisgarh"),
            ("bhilai", "Bhilai, Chhattisgarh"),
            ("bilaspur", "Bilaspur, Chhattisgarh"),
            ("korba", "Korba, Chhattisgarh"),
        ]
    ),
    # Uttarakhand
    (
        r"\b(?:uttarakhand|uttaranchal|dehradun|haridwar|roorkee|haldwani|rudrapur|kashipur|rishikesh|nainital|ukpsc|uksssc)\b",
        "Uttarakhand",
        [
            ("dehradun", "Dehradun, Uttarakhand"),
            ("haridwar", "Haridwar, Uttarakhand"),
            ("roorkee", "Roorkee, Uttarakhand"),
            ("rishikesh", "Rishikesh, Uttarakhand"),
            ("haldwani", "Haldwani, Uttarakhand"),
            ("nainital", "Nainital, Uttarakhand"),
        ]
    ),
    # Himachal Pradesh
    (
        r"\b(?:himachal\s*pradesh|\bhp\b|shimla|dharamshala|solan|mandi|kullu|hppsc|hpsssb)\b",
        "Himachal Pradesh",
        [
            ("shimla", "Shimla, Himachal Pradesh"),
            ("dharamshala", "Dharamshala, Himachal Pradesh"),
            ("solan", "Solan, Himachal Pradesh"),
            ("mandi", "Mandi, Himachal Pradesh"),
        ]
    ),
    # Jammu & Kashmir
    (
        r"\b(?:jammu\s*(?:and|&)\s*kashmir|\bj&k\b|\bjk\b|srinagar|jammu|anantnag|baramulla|udhampur|jkpsc|jkssb|j&k\s*bank|jammu\s*and\s*kashmir\s*bank)\b",
        "Jammu & Kashmir",
        [
            ("srinagar", "Srinagar, Jammu & Kashmir"),
            ("jammu", "Jammu, Jammu & Kashmir"),
            ("udhampur", "Udhampur, Jammu & Kashmir"),
        ]
    ),
    # Delhi
    (
        r"\b(?:delhi|new\s*delhi|delhi\s*ncr|dsssb)\b",
        "New Delhi / Delhi NCR",
        []
    ),
    # Chandigarh
    (
        r"\b(?:chandigarh)\b",
        "Chandigarh",
        []
    ),
    # Goa
    (
        r"\b(?:goa|panaji|margao|vasco)\b",
        "Goa",
        []
    ),
    # Tripura
    (
        r"\b(?:tripura|agartala|tpsc)\b",
        "Tripura",
        []
    ),
    # Meghalaya
    (
        r"\b(?:meghalaya|shillong)\b",
        "Meghalaya",
        []
    ),
    # Manipur
    (
        r"\b(?:manipur|imphal)\b",
        "Manipur",
        []
    ),
    # Nagaland
    (
        r"\b(?:nagaland|kohima|dimapur)\b",
        "Nagaland",
        []
    ),
    # Mizoram
    (
        r"\b(?:mizoram|aizawl)\b",
        "Mizoram",
        []
    ),
    # Arunachal Pradesh
    (
        r"\b(?:arunachal\s*pradesh|itanagar)\b",
        "Arunachal Pradesh",
        []
    ),
    # Sikkim
    (
        r"\b(?:sikkim|gangtok)\b",
        "Sikkim",
        []
    ),
    # Puducherry
    (
        r"\b(?:puducherry|pondicherry|karaikal)\b",
        "Puducherry",
        []
    ),
    # Andaman & Nicobar
    (
        r"\b(?:andaman|nicobar|port\s*blair)\b",
        "Port Blair, Andaman & Nicobar",
        []
    ),
    # Ladakh
    (
        r"\b(?:ladakh|leh|kargil)\b",
        "Ladakh",
        []
    )
]

# ==============================================================================
# 3. GENUINE PAN-INDIA CENTRAL RECRUITMENT BOARDS (Fallback to All India)
# ==============================================================================
PAN_INDIA_CENTRAL_BOARDS = [
    r"\bupsc\b",
    r"\bssc\b(?:\s*cgl|\s*chsl|\s*mts|\s*gd|\s*je|\s*stenographer|\s*cpo)?",
    r"\bibps\b",
    r"\brailway\s*recruitment\s*board\b|\brrb\b",
    r"\bindian\s*army\b",
    r"\bindian\s*air\s*force\b|\biaf\b",
    r"\bindian\s*navy\b",
    r"\bindian\s*coast\s*guard\b",
    r"\bcrpf\b",
    r"\bbsf\b",
    r"\bcisf\b",
    r"\bitbp\b",
    r"\bssb\b(?:\s*recruitment)?",
    r"\blifeline\s*insurance|lic\s*india\b",
    r"\brbi\s*grade\b",
]


def detect_job_location(org="", post_name="", detail_url="", text_content="", extracted_location=""):
    """
    Intelligently determines the specific Job Location for any job notification.
    
    Priority:
    1. Valid, non-generic extracted_location if already present (not "All India")
    2. Special institutions / universities (e.g. IIT Kanpur -> Kanpur, UP)
    3. State / City detection in Organization Name & URL Slug
    4. State / City detection in Post Name / Title
    5. State / City detection in raw text / notification snippet
    6. Central Pan-India identification (SSC, UPSC, IBPS, Army, Navy -> All India)
    7. Clean fallback
    """
    # 1. If extracted_location is already specific (not empty and not generic All India)
    if extracted_location:
        cleaned = extracted_location.strip()
        if cleaned and cleaned.lower() not in ["all india", "across india", "india", "various", "anywhere in india"]:
            return cleaned

    # Build combined search text
    org_clean = (org or "").lower()
    post_clean = (post_name or "").lower()
    url_slug = ""
    if detail_url:
        try:
            parsed = urlparse(detail_url)
            url_slug = parsed.path.lower().replace("-", " ").replace("_", " ")
        except Exception:
            url_slug = (detail_url or "").lower()

    text_clean = (text_content or "").lower()

    # Combined high-confidence context (Org + Slug + Post Name)
    high_priority_text = f"{org_clean} {url_slug} {post_clean}"

    # 2. Check Special Institutions / Universities
    for pattern, resolved_loc in SPECIAL_INSTITUTES:
        if re.search(pattern, high_priority_text) or (text_clean and re.search(pattern, text_clean[:500])):
            return resolved_loc

    # 3. Check State & City in High Priority Text (Org + URL Slug + Post Name)
    for state_pattern, state_name, city_list in STATE_CITY_RULES:
        if re.search(state_pattern, high_priority_text):
            # Check if a specific city within this state is also mentioned
            for city_term, city_loc in city_list:
                if city_term in high_priority_text:
                    return city_loc
            return state_name

    # 4. Check State & City in Full Text / Snippet
    if text_clean:
        # Check for explicit "job location : XYZ" or "location : XYZ"
        loc_match = re.search(r'(?:job\s*location|place\s*of\s*posting|place\s*of\s*work|work\s*location)\s*[:\-]\s*([^\n\<\r\t\.]{3,50})', text_clean)
        if loc_match:
            candidate = loc_match.group(1).strip()
            if candidate and candidate.lower() not in ["all india", "across india", "india", "various", "anywhere in india"]:
                # Normalize capitalization
                return candidate.title()

        # Check state & city in text snippet
        for state_pattern, state_name, city_list in STATE_CITY_RULES:
            if re.search(state_pattern, text_clean[:2000]):
                for city_term, city_loc in city_list:
                    if city_term in text_clean[:2000]:
                        return city_loc
                return state_name

    # 5. Check if it is genuinely a Pan-India Central Organization
    for pan_pattern in PAN_INDIA_CENTRAL_BOARDS:
        if re.search(pan_pattern, high_priority_text):
            return "All India (Across India)"

    # 6. Fallback
    return "All India"


def get_state_label_for_seo(location_str):
    """
    Returns appropriate state SEO label based on location (e.g. 'AP Jobs', 'Telangana Jobs', 'UP Jobs').
    """
    loc = (location_str or "").lower()
    if "telangana" in loc or "hyderabad" in loc:
        return "Telangana Jobs"
    elif "andhra" in loc or "visakhapatnam" in loc or "vijayawada" in loc:
        return "AP Jobs"
    elif "tamil nadu" in loc or "chennai" in loc:
        return "Tamil Nadu Jobs"
    elif "karnataka" in loc or "bengaluru" in loc:
        return "Karnataka Jobs"
    elif "maharashtra" in loc or "mumbai" in loc or "pune" in loc:
        return "Maharashtra Jobs"
    elif "uttar pradesh" in loc or "lucknow" in loc or "kanpur" in loc:
        return "Uttar Pradesh Jobs"
    elif "madhya pradesh" in loc or "bhopal" in loc or "indore" in loc:
        return "Madhya Pradesh Jobs"
    elif "gujarat" in loc or "ahmedabad" in loc:
        return "Gujarat Jobs"
    elif "rajasthan" in loc or "jaipur" in loc:
        return "Rajasthan Jobs"
    elif "bihar" in loc or "patna" in loc:
        return "Bihar Jobs"
    elif "west bengal" in loc or "kolkata" in loc:
        return "West Bengal Jobs"
    elif "odisha" in loc or "bhubaneswar" in loc:
        return "Odisha Jobs"
    elif "kerala" in loc or "kochi" in loc:
        return "Kerala Jobs"
    elif "delhi" in loc:
        return "Delhi Jobs"
    return "All India Jobs"
