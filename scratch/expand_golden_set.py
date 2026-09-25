import json
import os

new_queries = [
    {
        "query_id": "JAIPUR_01",
        "category": "known_destination_heritage",
        "query": "3-day royal forts and bazaars tour in Jaipur exploring Amber Fort and Johari Bazaar, budget $450.",
        "chat_history": [],
        "expected_constraints": {
            "destination": "Jaipur",
            "vibe_or_interests": "royal forts and bazaars, Amber Fort, Johari Bazaar",
            "budget": "$450",
            "number_of_days": 3
        },
        "ground_truth_facts": [
            "Amber Fort is situated in Amer, 11 km from Jaipur, famous for Sheesh Mahal (Mirror Palace).",
            "Composite entry tickets for monuments in Jaipur cover Amber Fort, Albert Hall, and Hawa Mahal.",
            "Johari Bazaar is renowned for traditional Rajasthani Kundan jewelry and gemstone trade.",
            "Traditional heritage haveli stays in Bani Park cost between ₹2,500 and ₹4,500 per night."
        ],
        "snapshotted_sources": [
            {
                "source_id": "Src-1",
                "title": "Jaipur 3-Day Heritage & Forts Itinerary",
                "domain": "rajasthantourism.gov.in",
                "text": "Jaipur's iconic Amber Fort stands atop Cheel ka Teela with Rajput and Mughal architecture. Composite monument tickets cost ₹300-1000. Johari Bazaar and Bapu Bazaar offer authentic lac bangles, bandhani textiles, and precious gems. Heritage haveli hotels in Bani Park provide royal courtyard accommodations for ₹3,000 per night."
            }
        ]
    },
    {
        "query_id": "JAIPUR_02_REV",
        "category": "revision_activity_swap",
        "query": "Swap bazaar shopping on Day 2 for an astronomical tour at Jantar Mantar and sunrise hot air balloon.",
        "chat_history": [
            "3-day royal forts and bazaars tour in Jaipur exploring Amber Fort and Johari Bazaar, budget $450."
        ],
        "expected_constraints": {
            "destination": "Jaipur",
            "vibe_or_interests": "royal forts, Jantar Mantar astronomical tour, sunrise hot air balloon",
            "budget": "$450",
            "number_of_days": 3
        },
        "ground_truth_facts": [
            "Jantar Mantar is a UNESCO World Heritage astronomical observatory featuring the world's largest stone sundial.",
            "Sunrise hot air balloon safaris over Amber Fort depart from near Kukas or Amer village.",
            "Audio guides or certified astronomical guides are available at Jantar Mantar for ₹200-400."
        ],
        "snapshotted_sources": [
            {
                "source_id": "Src-2",
                "title": "Jaipur Astronomy and Ballooning Guide",
                "domain": "travelrajasthan.co",
                "text": "Jantar Mantar built by Maharaja Sawai Jai Singh II houses nineteen architectural astronomical instruments, including the Vrihat Samrat Yantra sundial. Early morning hot air balloon rides over the Aravalli hills provide sweeping views of Amber Fort and Jal Mahal."
            }
        ]
    },
    {
        "query_id": "RISHIKESH_01",
        "category": "known_destination_adventure",
        "query": "3-day white-water rafting and yoga retreat in Rishikesh with riverside camping under $350.",
        "chat_history": [],
        "expected_constraints": {
            "destination": "Rishikesh",
            "vibe_or_interests": "white-water rafting, yoga retreat, riverside camping",
            "budget": "$350",
            "number_of_days": 3
        },
        "ground_truth_facts": [
            "Rishikesh is located along the Ganges River in Uttarakhand foothills, known as the Yoga Capital of the World.",
            "Popular rafting stretches include Marine Drive to Shivpuri (12 km) and Shivpuri to Rishikesh (16 km) with Grade III rapids.",
            "Evening Ganga Aarti takes place daily at Triveni Ghat and Parmarth Niketan.",
            "Riverside camps and eco-domes in Shivpuri and Mohan Chatti cost ₹1,800 to ₹3,500 per night inclusive of meals."
        ],
        "snapshotted_sources": [
            {
                "source_id": "Src-1",
                "title": "Rishikesh Rafting & Yoga Retreat Guide",
                "domain": "uttarakhandtourism.gov.in",
                "text": "Rishikesh offers world-class white water rafting on the Ganges with iconic rapids like Roller Coaster and Golf Course. 16 km Shivpuri rafting packages cost ₹1,000-1,500 per person. Yoga sessions at Parmarth Niketan and ashram day passes cost ₹300-500. Shivpuri riverside camps include beach volleyball and buffet meals for ₹2,200/night."
            }
        ]
    },
    {
        "query_id": "VARANASI_01",
        "category": "known_destination_culture",
        "query": "2-day spiritual photography and cultural trip to Varanasi with sunrise boat ride, budget $250.",
        "chat_history": [],
        "expected_constraints": {
            "destination": "Varanasi",
            "vibe_or_interests": "spiritual photography, cultural trip, sunrise boat ride",
            "budget": "$250",
            "number_of_days": 2
        },
        "ground_truth_facts": [
            "Varanasi sits on the western bank of the holy Ganges with over 84 ghats from Assi Ghat to Manikarnika Ghat.",
            "Hand-rowed sunrise boat rides along the ghats take 2 hours and cost ₹400-800.",
            "The evening Maha Aarti at Dashashwamedh Ghat is held every evening at 6:45 PM.",
            "Traditional Banarasi silk weaver workshops are concentrated in Madanpura and Chowk quarters."
        ],
        "snapshotted_sources": [
            {
                "source_id": "Src-1",
                "title": "Varanasi Spiritual Heritage & Ghats Walking Tour",
                "domain": "uptourism.gov.in",
                "text": "Sunrise rowing boats from Assi to Dashashwamedh Ghat reveal morning bathers, sadhus, and centuries-old riverside palaces. The evening Aarti at Dashashwamedh Ghat features multi-tiered brass oil lamps. Authentic silk saree weaving clusters in the old galis offer weaving demonstrations and direct artisan purchases."
            }
        ]
    },
    {
        "query_id": "ANDAMAN_01",
        "category": "known_destination_nature",
        "query": "5-day scuba diving and beach holiday on Havelock Island (Swaraj Dweep), budget $800.",
        "chat_history": [],
        "expected_constraints": {
            "destination": "Havelock Island (Swaraj Dweep)",
            "vibe_or_interests": "scuba diving and beach holiday",
            "budget": "$800",
            "number_of_days": 5
        },
        "ground_truth_facts": [
            "Havelock Island (Swaraj Dweep) is accessed by Makruzz or Green Ocean government/private catamarans from Port Blair (90 minutes).",
            "Radhanagar Beach (Beach No. 7) has been certified Blue Flag and is celebrated for turquoise waters and sunsets.",
            "Elephant Beach is the hub for coral reef snorkeling and beginner Discover Scuba Dives.",
            "PADI Discover Scuba Dives (DSD) cost between ₹3,500 and ₹5,000 per dive."
        ],
        "snapshotted_sources": [
            {
                "source_id": "Src-1",
                "title": "Havelock Island Diving and Beaches",
                "domain": "andamantourism.gov.in",
                "text": "Havelock Island is the premier scuba diving hub in the Andaman archipelago with dive sites like Nemo Reef, Dixon's Pinnacle, and Aquarium. Radhanagar Beach offers powdery white sands and sunset views. Catamaran ferry tickets from Port Blair cost ₹1,200 to ₹1,800 one-way. Beach huts at Vijaynagar beach start at ₹2,500/night."
            }
        ]
    },
    {
        "query_id": "ANDAMAN_02_REV",
        "category": "revision_budget_reduction",
        "query": "Make the Havelock accommodations cheaper with eco-huts to reduce total stay cost under $500.",
        "chat_history": [
            "5-day scuba diving and beach holiday on Havelock Island (Swaraj Dweep), budget $800."
        ],
        "expected_constraints": {
            "destination": "Havelock Island (Swaraj Dweep)",
            "vibe_or_interests": "scuba diving, beach holiday, budget eco-huts",
            "budget": "under $500",
            "number_of_days": 5
        },
        "ground_truth_facts": [
            "Budget bamboo huts and backpacker guesthouses on Beach No. 3 and Vijaynagar Beach cost ₹1,000 to ₹1,800 per night.",
            "Scooter rentals cost ₹400-500 per day for exploring the island affordably.",
            "Local government bus services between the jetty, Radhanagar, and Kalapathar cost ₹20 per trip."
        ],
        "snapshotted_sources": [
            {
                "source_id": "Src-2",
                "title": "Havelock Island on a Budget",
                "domain": "andamanbackpackers.com",
                "text": "Travelers on a budget can stay in thatched bamboo huts and eco-resorts near Govind Nagar or Beach No. 5 for ₹1,200/night. Renting a Honda Activa scooter allows cheap independent transport across the island without expensive taxi fares."
            }
        ]
    },
    {
        "query_id": "HAMPI_01",
        "category": "known_destination_heritage",
        "query": "3-day bouldering, cycling, and ruins exploration in Hampi under $300.",
        "chat_history": [],
        "expected_constraints": {
            "destination": "Hampi",
            "vibe_or_interests": "bouldering, cycling, UNESCO ruins exploration",
            "budget": "$300",
            "number_of_days": 3
        },
        "ground_truth_facts": [
            "Hampi is a UNESCO World Heritage site showcasing the 14th-century Vijayanagara Empire ruins along the Tungabhadra River.",
            "Vijaya Vittala Temple is famed for its stone chariot and musical granite pillars.",
            "The Hippie Island side (Anegundi / Sanapur Lake) is the premier bouldering and cliff-jumping landscape.",
            "Bicycle rentals cost ₹100-150/day and moped rentals cost ₹300/day."
        ],
        "snapshotted_sources": [
            {
                "source_id": "Src-1",
                "title": "Hampi Heritage Ruins & Bouldering Itinerary",
                "domain": "karnatakatourism.org",
                "text": "Hampi's ancient ruins span 25 sq km across granite boulders and banana plantations. Key sites include Virupaksha Temple, the Queen's Bath, and the Stone Chariot at Vittala Temple. Sanapur Lake across the river offers coracle boat rides (₹300) and bouldering crags with rental crash pads for ₹200/day."
            }
        ]
    },
    {
        "query_id": "KAZIRANGA_01",
        "category": "known_destination_wildlife",
        "query": "3-day wildlife safari in Kaziranga National Park Assam to spot one-horned rhinos, budget $500.",
        "chat_history": [],
        "expected_constraints": {
            "destination": "Kaziranga National Park",
            "vibe_or_interests": "wildlife safari, one-horned rhinos, tea estate stay",
            "budget": "$500",
            "number_of_days": 3
        },
        "ground_truth_facts": [
            "Kaziranga National Park is a UNESCO World Heritage site hosting two-thirds of the world's great one-horned rhinoceroses.",
            "The park is divided into four main tourist ranges: Central (Kohora), Western (Bagori), Eastern (Agoratoli), and Burapahar.",
            "Jeep safaris operate twice daily (morning 7:30 AM and afternoon 1:30 PM) costing around ₹2,500-3,500 per jeep.",
            "Tea garden homestays and eco-resorts near Kohora range cost ₹2,500 to ₹4,500 per night."
        ],
        "snapshotted_sources": [
            {
                "source_id": "Src-1",
                "title": "Kaziranga Rhino Safari & Assam Travel Guide",
                "domain": "assamtourism.gov.in",
                "text": "Kaziranga's Bagori western range is renowned for dense rhino populations and wild water buffaloes. Central Kohora range offers excellent birdwatching and swamp deer sightings. Open 4x4 Gypsy safaris must be booked through the range forest office. Surrounding Hathikuli and Diffalu tea estates offer heritage bungalow stays."
            }
        ]
    },
    {
        "query_id": "DARJEELING_01",
        "category": "known_destination_scenic",
        "query": "4-day tea garden walks and Himalayan views in Darjeeling with Tiger Hill sunrise, budget $450.",
        "chat_history": [],
        "expected_constraints": {
            "destination": "Darjeeling",
            "vibe_or_interests": "tea garden walks, Himalayan views, Tiger Hill sunrise",
            "budget": "$450",
            "number_of_days": 4
        },
        "ground_truth_facts": [
            "Darjeeling is located in the Lesser Himalayas at 2,042 meters, famous for orthodox black tea and views of Mount Kanchenjunga.",
            "Tiger Hill (2,590m) offers sunrise panoramas over Kanchenjunga and Mount Everest, requiring an early 4:00 AM departure.",
            "The Darjeeling Himalayan Railway (Toy Train) is a UNESCO World Heritage mountain steam railway.",
            "Colonial tea estate homestays like Makaibari or Happy Valley cost ₹2,500 to ₹5,000 per night."
        ],
        "snapshotted_sources": [
            {
                "source_id": "Src-1",
                "title": "Darjeeling Tea & Toy Train Mountain Guide",
                "domain": "wbtourism.gov.in",
                "text": "Darjeeling's Happy Valley Tea Estate allows guided tea plucking walks and tasting sessions. Early morning shared jeeps to Tiger Hill cost ₹250-400 per seat. The joyride steam train from Darjeeling to Ghum loops around the Batasia Memorial Loop. Heritage cafes on the Mall Road include Glenary's Bakery and Keventer's rooftop."
            }
        ]
    },
    {
        "query_id": "UNDECIDED_02_MUMBAI",
        "category": "undecided_destination",
        "query": "I am in Mumbai and want a 3-day quiet coastal getaway within 4 hours drive under $350.",
        "chat_history": [],
        "expected_constraints": {
            "current_location": "Mumbai",
            "vibe_or_interests": "quiet coastal getaway within 4 hours drive",
            "budget": "$350",
            "number_of_days": 3
        },
        "ground_truth_facts": [
            "Alibaug, Kashid, and Murud along the Konkan coast are prime coastal getaways within 3 to 4 hours of Mumbai.",
            "Ro-Pax ferry from Bhaucha Dhakka (Mumbai) to Mandwa takes 60 minutes and carries passengers and vehicles.",
            "Kashid Beach features white sands and water sports, located 30 km south of Alibaug.",
            "Beachside Konkani homestays and cottage stays cost ₹2,000 to ₹4,000 per night."
        ],
        "snapshotted_sources": [
            {
                "source_id": "Src-1",
                "title": "Konkan Coastal Escapes from Mumbai: Alibaug vs Kashid",
                "domain": "maharashtratourism.gov.in",
                "text": "The M2M Ro-Pax ferry allows quick transit from South Mumbai to Mandwa in under one hour for ₹400/passenger. Kashid Beach offers clean waves, suru (casuarina) groves, and quiet beach tents. Nearby Murud-Janjira sea fort is an unbreached island fortress accessed by sailboat."
            }
        ]
    },
    {
        "query_id": "UNDECIDED_03_DELHI",
        "category": "undecided_destination",
        "query": "I am in Delhi and want a 2-day weekend heritage or wildlife escape within 5 hours drive under $300.",
        "chat_history": [],
        "expected_constraints": {
            "current_location": "Delhi",
            "vibe_or_interests": "weekend heritage or wildlife escape within 5 hours drive",
            "budget": "$300",
            "number_of_days": 2
        },
        "ground_truth_facts": [
            "Neemrana Fort-Palace (Rajasthan) is located 120 km from Delhi on the NH48 (2.5 hours drive).",
            "Sariska Tiger Reserve in Alwar is reachable within 4.5 hours from Delhi via the Delhi-Mumbai Expressway.",
            "Neemrana offers historic 15th-century palace architecture and India's first aerial zip-lining (Flying Fox).",
            "Jeep safaris in Sariska Tiger Reserve cost ₹1,200 to ₹1,800 per seat booked through forest department portal."
        ],
        "snapshotted_sources": [
            {
                "source_id": "Src-1",
                "title": "Weekend Road Trips from Delhi: Neemrana and Sariska",
                "domain": "delhitourism.gov.in",
                "text": "Neemrana Fort-Palace stepped across 14 tiers on the Aravalli hills provides royal luxury day trips and zip-line tours over fort ramparts. For wildlife enthusiasts, Sariska Tiger Reserve in Alwar features Bengal tigers, leopards, and 10th-century Kankwari Fort ruins within a scenic dry deciduous forest."
            }
        ]
    },
    {
        "query_id": "MCLEODGANJ_01",
        "category": "known_destination_culture",
        "query": "4-day Tibetan culture and Triund trek in McLeod Ganj Dharamshala, budget $350.",
        "chat_history": [],
        "expected_constraints": {
            "destination": "McLeod Ganj (Dharamshala)",
            "vibe_or_interests": "Tibetan culture, Triund trek, monasteries",
            "budget": "$350",
            "number_of_days": 4
        },
        "ground_truth_facts": [
            "McLeod Ganj is the seat of the Dalai Lama and the Central Tibetan Administration in the Kangra Valley.",
            "Tsuglagkhang Complex houses the main temple, Namgyal Monastery, and the Tibet Museum.",
            "Triund trek is a 9 km trail starting from Galu Devi temple with views of the snow-clad Dhauladhar range.",
            "Tibetan guesthouses and boutique stays in Dharamkot or Upper Bhagsu cost ₹1,200 to ₹2,800 per night."
        ],
        "snapshotted_sources": [
            {
                "source_id": "Src-1",
                "title": "McLeod Ganj & Triund Trek Complete Guide",
                "domain": "himachaltourism.gov.in",
                "text": "McLeod Ganj offers rich Tibetan culture, authentic thukpa and momo cafes, and the serene Dalai Lama Temple. The trek to Triund ridge (2,875m) takes 4-5 hours from Dharamkot and can be done as a day hike or overnight camp with panoramic views of the Kangra Valley. Bhagsu Waterfall and St. John in the Wilderness church are easy side excursions."
            }
        ]
    },
    {
        "query_id": "MCLEODGANJ_02_REV",
        "category": "revision_pace_slow",
        "query": "Remove the high-altitude Triund trek and add quiet meditation, Tibetan pottery, and Norbulingka Institute.",
        "chat_history": [
            "4-day Tibetan culture and Triund trek in McLeod Ganj Dharamshala, budget $350."
        ],
        "expected_constraints": {
            "destination": "McLeod Ganj (Dharamshala)",
            "vibe_or_interests": "quiet meditation, Tibetan pottery, Norbulingka Institute",
            "budget": "$350",
            "number_of_days": 4
        },
        "ground_truth_facts": [
            "Norbulingka Institute in Sidhpur preserves traditional Tibetan art forms, thangka painting, and wood carving.",
            "Tushita Meditation Centre in Dharamkot conducts guided morning meditation sessions for visitors.",
            "Local auto-rickshaws between McLeod Ganj and Norbulingka Institute cost ₹400-500 round trip."
        ],
        "snapshotted_sources": [
            {
                "source_id": "Src-2",
                "title": "Cultural & Artistic Heritage of Dharamshala",
                "domain": "norbulingka.org",
                "text": "Norbulingka Institute features Japanese-style landscaped gardens, the Losel Doll Museum, and workshops where master artisans practice metal craft, thangka painting, and weaving. Tushita Meditation Centre offers drop-in Vipassana and Buddhist philosophy teachings."
            }
        ]
    },
    {
        "query_id": "WAYANAD_01",
        "category": "known_destination_nature",
        "query": "3-day rainforest treehouse stay and bamboo rafting in Wayanad Kerala under $400.",
        "chat_history": [],
        "expected_constraints": {
            "destination": "Wayanad",
            "vibe_or_interests": "rainforest treehouse stay, bamboo rafting, Edakkal Caves",
            "budget": "$400",
            "number_of_days": 3
        },
        "ground_truth_facts": [
            "Wayanad is a forested plateau in the Western Ghats of northeastern Kerala known for spice plantations.",
            "Banasura Sagar Dam is the largest earth dam in India and offers speedboating and island views.",
            "Kuruva Island (Kuruvadweep) features protected river delta islands with bamboo rafting on the Kabini River.",
            "Treehouse resorts and plantation stays in Vythiri or Meppadi cost ₹3,000 to ₹5,500 per night."
        ],
        "snapshotted_sources": [
            {
                "source_id": "Src-1",
                "title": "Wayanad Rainforest & Bamboo Rafting Guide",
                "domain": "keralatourism.org",
                "text": "Wayanad's mist-covered hills offer authentic treehouses set amidst cardamom and pepper estates. Edakkal Caves showcase Neolithic petroglyphs carved into rock faces. Bamboo rafting at Kuruva Island costs ₹400 per person, drifting through freshwater swamp streams."
            }
        ]
    },
    {
        "query_id": "SPITI_01",
        "category": "known_destination_adventure",
        "query": "7-day high-altitude road trip through Spiti Valley visiting Key Monastery and Chandratal, budget $850.",
        "chat_history": [],
        "expected_constraints": {
            "destination": "Spiti Valley",
            "vibe_or_interests": "high-altitude road trip, Key Monastery, Chandratal Lake",
            "budget": "$850",
            "number_of_days": 7
        },
        "ground_truth_facts": [
            "Spiti Valley is a cold desert mountain valley in Himachal Pradesh situated at an average altitude above 3,800 meters.",
            "Key (Kye) Monastery is a 1,000-year-old Tibetan Buddhist monastery overlooking the Spiti River near Kaza.",
            "Chandratal (Moon Lake) at 4,250 meters is an alpine lake accessed via Kunzum Pass (4,551m).",
            "Homestays in high villages like Kibber, Langza, and Mudh cost ₹1,000 to ₹2,000 per night including local meals."
        ],
        "snapshotted_sources": [
            {
                "source_id": "Src-1",
                "title": "Spiti Valley Overland Expedition Guide",
                "domain": "spitivalleytourism.com",
                "text": "The classic Spiti circuit crosses Rohtang/Atal Tunnel and Kunzum La into Kaza. Key Gompa houses ancient murals and manuscripts. Langza village is famous for prehistoric marine fossils, while Hikkim features the world's highest post office at 4,400 meters. Camping near Chandratal is restricted to designated sites 3 km before the lake."
            }
        ]
    },
    {
        "query_id": "MEGHALAYA_01",
        "category": "known_destination_adventure",
        "query": "5-day Living Root Bridges trek and clear river kayaking in Meghalaya (Cherrapunji & Dawki), budget $600.",
        "chat_history": [],
        "expected_constraints": {
            "destination": "Meghalaya (Cherrapunji & Dawki)",
            "vibe_or_interests": "Living Root Bridges trek, clear river kayaking",
            "budget": "$600",
            "number_of_days": 5
        },
        "ground_truth_facts": [
            "The Double Decker Living Root Bridge in Nongriat village is trained from Ficus elastica roots by indigenous Khasi tribes.",
            "The trek to Nongriat involves descending and climbing approximately 3,500 concrete steps from Tyrna village.",
            "Umngot River in Dawki near the Indo-Bangladesh border is celebrated for emerald glass-like water clarity.",
            "Village homestays in Nongriat and riverside camping in Shnongpdeng cost ₹1,000 to ₹2,500 per night."
        ],
        "snapshotted_sources": [
            {
                "source_id": "Src-1",
                "title": "Meghalaya Living Root Bridges & Dawki Guide",
                "domain": "meghalayatourism.gov.in",
                "text": "Cherrapunji (Sohra) features dramatic waterfalls like Nohkalikai and Seven Sisters. The hike to Nongriat's Double Decker Root Bridge takes 3-4 hours each way. Shnongpdeng village on the Umngot River offers scuba diving, cliff jumping, and kayaking in crystal clear waters for ₹500-1,000."
            }
        ]
    },
    {
        "query_id": "JODHPUR_01",
        "category": "known_destination_heritage",
        "query": "3-day Blue City walk and Mehrangarh Fort zip-lining in Jodhpur, budget $400.",
        "chat_history": [],
        "expected_constraints": {
            "destination": "Jodhpur",
            "vibe_or_interests": "Blue City walk, Mehrangarh Fort zip-lining",
            "budget": "$400",
            "number_of_days": 3
        },
        "ground_truth_facts": [
            "Mehrangarh Fort is an imposing 15th-century citadel perched 125 meters above Jodhpur's blue Brahmin houses.",
            "Flying Fox Jodhpur operates a 6-line aerial zip-line course across the moats and lakes behind Mehrangarh Fort.",
            "Jaswant Thada is a royal marble cenotaph situated 1 km from Mehrangarh Fort with lake gardens.",
            "Rooftop heritage hotels around Navchokiya and Clock Tower (Sardar Market) cost ₹2,000 to ₹4,000 per night."
        ],
        "snapshotted_sources": [
            {
                "source_id": "Src-1",
                "title": "Jodhpur Blue City & Mehrangarh Fort Guide",
                "domain": "rajasthantourism.gov.in",
                "text": "Jodhpur's Mehrangarh Fort features palaces with intricate latticework, the Phool Mahal, and royal palanquins. Flying Fox zip-lining tickets cost ₹1,700-2,100 per person for all 6 circuits. Navchokiya district is the original Brahmin quarter with winding indigo-painted lanes perfect for morning walking tours."
            }
        ]
    },
    {
        "query_id": "KASOL_01",
        "category": "known_destination_hiking",
        "query": "4-day Parvati Valley backpacking trip to Kasol, Chalal, and Kheerganga hot springs trek, budget $300.",
        "chat_history": [],
        "expected_constraints": {
            "destination": "Kasol & Parvati Valley",
            "vibe_or_interests": "backpacking, Chalal, Kheerganga hot springs trek",
            "budget": "$300",
            "number_of_days": 4
        },
        "ground_truth_facts": [
            "Kasol is a Himalayan village along the Parvati River in Himachal Pradesh, known as Mini Israel for its cafes.",
            "Chalal village is a short 20-minute suspension bridge walk from Kasol through pine forests.",
            "Kheerganga is a 12 km trek from Barshaini leading to natural thermal sulfur hot springs at 2,960 meters.",
            "Dorm beds and wooden riverside cottages in Kasol and Chalal cost ₹500 to ₹1,500 per night."
        ],
        "snapshotted_sources": [
            {
                "source_id": "Src-1",
                "title": "Parvati Valley Backpacking: Kasol to Kheerganga",
                "domain": "himachaltourism.gov.in",
                "text": "Kasol serves as the base for trekking in Parvati Valley. The 12 km trail to Kheerganga starts from Barshaini passing through Nakthan village and Rudranag waterfall. The natural hot water sulfur pool at the summit is open to trekkers. German bakeries in Kasol and Chalal serve shakshuka and trout fish."
            }
        ]
    },
    {
        "query_id": "GOKARNA_01",
        "category": "known_destination_beach",
        "query": "3-day beach trekking holiday in Gokarna exploring Om Beach and Kudle Beach, budget $250.",
        "chat_history": [],
        "expected_constraints": {
            "destination": "Gokarna",
            "vibe_or_interests": "beach trekking holiday, Om Beach, Kudle Beach",
            "budget": "$250",
            "number_of_days": 3
        },
        "ground_truth_facts": [
            "Gokarna is a coastal temple town in Karnataka famous for the Mahabaleshwar Shiva Temple and secluded beaches.",
            "The popular Five Beach Trek covers Gokarna Main Beach, Kudle Beach, Om Beach, Half Moon Beach, and Paradise Beach across coastal hills.",
            "Om Beach is naturally shaped like the Hindu spiritual symbol 'Om'.",
            "Rustic beach shacks and cafe huts at Kudle and Om beaches cost ₹1,000 to ₹2,500 per night."
        ],
        "snapshotted_sources": [
            {
                "source_id": "Src-1",
                "title": "Gokarna Beach Trekking & Coastal Shacks Guide",
                "domain": "karnatakatourism.org",
                "text": "Gokarna offers a tranquil alternative to Goa. The cliffside trail connecting Kudle to Om, Half Moon, and Paradise Beach takes around 4-5 hours. Beach shacks serve fresh seafood and filter coffee. Boat transfers between Om Beach and Paradise Beach cost ₹300-500."
            }
        ]
    },
    {
        "query_id": "GOKARNA_02_REV",
        "category": "revision_activity_swap",
        "query": "Swap the strenuous cliff hike on Day 2 for an excursion to Mirjan Fort and sunset boat cruise.",
        "chat_history": [
            "3-day beach trekking holiday in Gokarna exploring Om Beach and Kudle Beach, budget $250."
        ],
        "expected_constraints": {
            "destination": "Gokarna",
            "vibe_or_interests": "Mirjan Fort excursion, sunset boat cruise, relaxing beach stay",
            "budget": "$250",
            "number_of_days": 3
        },
        "ground_truth_facts": [
            "Mirjan Fort is a 16th-century laterite stone fort located 22 km south of Gokarna on the banks of the Aganashini River.",
            "Mirjan Fort is noted for high bastions, double ramparts, and moss-covered stone walls.",
            "Sunset boat cruises depart from Om Beach or Tadadi port offering dolphin spotting."
        ],
        "snapshotted_sources": [
            {
                "source_id": "Src-2",
                "title": "Mirjan Fort and Gokarna Coastal Cruising",
                "domain": "karnatakatravel.info",
                "text": "Mirjan Fort built under Queen Chennabhairadevi (the Pepper Queen) features watchtowers, hidden passageways, and laterite stone architecture surrounded by lush coconut trees. Entry is free. Boat rides around Tadadi backwaters and Om Beach offer sunset views and occasional dolphin sightings for ₹400/person."
            }
        ]
    }
]

file_path = os.path.join("data", "golden_eval_set.json")
with open(file_path, "r", encoding="utf-8") as f:
    existing = json.load(f)

print(f"Existing count: {len(existing)}")

# Check existing query_ids to avoid duplicates
existing_ids = {x["query_id"] for x in existing}
added = 0
for nq in new_queries:
    if nq["query_id"] not in existing_ids:
        existing.append(nq)
        added += 1

print(f"Added {added} new queries. Total count is now: {len(existing)}")

with open(file_path, "w", encoding="utf-8") as f:
    json.dump(existing, f, indent=2)

print("Saved updated golden_eval_set.json successfully!")
