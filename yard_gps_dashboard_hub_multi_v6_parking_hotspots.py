import os
import hashlib
import hmac
import math
import re
import time

import folium
from folium.plugins import FastMarkerCluster
import pandas as pd
import requests
import streamlit as st
from streamlit_folium import st_folium

st.set_page_config(page_title='Everest Fleet | Yard Control', page_icon='🚗', layout='wide')

# ============================================================
# LOGIN
# Users are listed in secrets under [auth.users] as
#   username = "pbkdf2_sha256$<iterations>$<salt>$<hash>"
# Generate a line with:  python make_password_hash.py
# Nothing below this block runs (no GPS API call, no map) until a
# user has signed in.
# ============================================================
def _verify_password(password, stored):
    try:
        algo, iterations, salt_hex, digest_hex = str(stored).split('$')
        if algo != 'pbkdf2_sha256':
            return False
        calc = hashlib.pbkdf2_hmac(
            'sha256', password.encode('utf-8'), bytes.fromhex(salt_hex), int(iterations)
        ).hex()
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(calc, digest_hex)


def require_login():
    if st.session_state.get('auth_user'):
        return

    try:
        users = {str(k).lower(): v for k, v in st.secrets['auth']['users'].items()}
    except (KeyError, FileNotFoundError, AttributeError):
        users = {}

    st.markdown('## 🚗 Everest Fleet — Yard Control')
    if not users:
        st.error('Login is not set up yet: add an `[auth.users]` section to the app secrets '
                 '(see DEPLOY.md).')
        st.stop()

    with st.form('login_form'):
        username = st.text_input('Username').strip().lower()
        password = st.text_input('Password', type='password')
        submitted = st.form_submit_button('Sign in', width='stretch')

    if submitted:
        stored = users.get(username)
        if stored and _verify_password(password, stored):
            st.session_state['auth_user'] = username
            st.rerun()
        time.sleep(1.5)  # slow down password guessing
        st.error('Wrong username or password.')
    st.stop()


require_login()

# GPS data is fetched only on the first load of a fleet and when the
# "Refresh GPS now" button is clicked. There is no automatic refresh.


# ============================================================
# HUB CONFIGURATION
# Add another hub by copying the "Mumbai" block and replacing
# its center / boundary / zone coordinates.
# ============================================================

HUBS = {
    "Mumbai": {
        "center": (19.0842, 73.0304),
        "zoom": 18,
        "yard_name": "Mumbai-KK",
        "fleet": "Mumbai GoMyGPS",

        # Main physical yard boundary
        "yard_boundary": [(19.0834834, 73.0301655), (19.083765, 73.030029), (19.084330, 73.029999), (19.084885, 73.030233), (19.085554, 73.030474), (19.086350, 73.030611), (19.0865633, 73.0309302), (19.0865931, 73.0309818), (19.0865192, 73.0310996), (19.0864991, 73.0311974), (19.086099, 73.031160), (19.085952, 73.031156), (19.085473, 73.031077), (19.085085, 73.030991), (19.084639, 73.030847), (19.083773, 73.030549), (19.083387,73.030316)
                    ],

        "gate": [
            (19.0834834, 73.0301655),
            (19.083387,73.030316)
        ],

        "zones": {
            "Insurance and Breakdown": {
                "polygon": [
                    (19.0847826, 73.0305817),(19.0848410, 73.0302768),(19.084885, 73.030233), (19.0840083, 73.0300134),(19.0839432, 73.0302839)
                ],
                "capacity": 35
            },
            "RTA Parking": {
                "polygon": [
                      (19.085541, 73.030456), (19.086350, 73.030611), (19.0865633, 73.0309302), (19.0865931, 73.0309818), (19.0865192, 73.0310996), (19.0864991, 73.0311974), (19.086099, 73.031160), (19.085952, 73.031156), (19.085382, 73.030999)
                ],
                "capacity": 350
            },
            "Repair Parking": {
                "polygon": [
                    (19.0852203, 73.0305670), (19.085021, 73.030371), (19.084957, 73.030562), (19.085159, 73.030712)
                ],
                "capacity": 45
            },
            
        }
    },
    "Mumbai-Vasai": {
        "center": (19.406849, 72.864257),
        "zoom": 18,
        "yard_name": "Vasai",
        "fleet": "Mumbai GoMyGPS",

        # Main physical yard boundary
        "yard_boundary": [ (19.4066684, 72.8640315), 
                           (19.4067373, 72.8643007), 
                           (19.4071095, 72.8640253), 
                           (19.4071046, 72.8638507)],

        "gate": [(19.4051986, 72.8650246),
(19.4052121, 72.8650417)
        ],

        "zones": {
            "WS": {
                "polygon": [ (19.4067818, 72.8640730),
                             (19.4067166, 72.8640777),
                             (19.407288, 72.864183),
                             (19.4070709, 72.8640034)],
                "capacity": 30
            },
            "Central Parking": {
                "polygon": [(19.406656, 72.864117),
                            (19.4066498, 72.8641370),
                            (19.4071043, 72.8640726),
                            (19.4071629, 72.8640048)
                ],
                "capacity": 200
            },
            "Office": {
                "polygon": [(19.4066741, 72.8640402),
                            (19.4067255, 72.8640947),
                            (19.4067224, 72.8640784),
                            (19.4067756, 72.8642348)
                ],
                "capacity": 30
            },
            "Stock Yard": {
                "polygon": [(19.4052175, 72.8650384),
                            (19.4050887, 72.8647493),
                            (19.4051458, 72.8647428),
                            (19.4051892, 72.86479)
                ],
                "capacity": 60
            }
        }
    },
    
"Pune": {
        "center": (18.551999, 73.762331),
        "zoom": 18,
        "yard_name": "PUNE",
        "fleet": "Pune GoMyGPS",

        # Main physical yard boundary
        "yard_boundary": [(18.552239,73.762233), (18.552121, 73.762338), (18.552180521466656, 73.76256017271089), (18.552069908496545, 73.76258967701014), (18.552024773298797, 73.76259571198044), (18.551935138573278, 73.76261851075698), (18.551778754472185, 73.76266410831018), (18.55186457503151, 73.76250988129179), (18.551563249316903, 73.76234224322809), (18.551783204426403, 73.76194326463678), (18.55187665347968, 73.76196472230913), (18.552043208804424, 73.76202909532587), (18.55205592294446, 73.76203110698265), (18.552205314019034, 73.76204317692324), (18.552249,73.762305)
                    ],

        "gate": [
            (18.552239,73.762233),
            (18.552249,73.762305)
        ],
        "Drive Passage": [
            (18.552239,73.762233),
            (18.552249,73.762305), (18.552929633583815, 73.7621265970175), (18.552943997267665, 73.76216726571867)
        ],

        "zones": {
            "Repair": {
                "polygon": [
                    (18.552205314019034,73.76204317692324),(18.552227563743312, 73.7621424186564),(18.552136022005904, 73.7621652174331),(18.552154457498627, 73.76225909474888), (18.552107415203643, 73.76231206837707), (18.55206927279217, 73.7623449254376), (18.551898267540682, 73.76231475058606), (18.55199171652723, 73.76205189410186), (18.552001887843776, 73.76201702538465), (18.552050837289602, 73.76203043642977)],
                "capacity": 70
            },
            "Work Shop": {
                "polygon": [(18.551814759105493, 73.76246765520801), (18.551563249316903, 73.76234224322809), (18.551783204426403, 73.76194326463678), (18.551988584509022, 73.76204493617354)
                    ],
                "capacity": 70
            },

            "RTA Parking": {
                "polygon": [
                    (18.552029075842245, 73.7623746479689),(18.552121, 73.762338), (18.552180521466656, 73.76256017271089), (18.552069908496545, 73.76258967701014)
                ],
                "capacity": 30
            },
            "Engine": {
                "polygon": [
                    (18.55191281221659, 73.76247880032713),(18.55199914200647, 73.76246522094065), (18.552024773298797, 73.76259571198044),(18.551935138573278, 73.76261851075698)
                ],
                "capacity": 15
            },
            "PUNE": {
                "polygon": [
                    (18.552239,73.762233), (18.552121, 73.762338), (18.552180521466656, 73.76256017271089), (18.552069908496545, 73.76258967701014), (18.552024773298797, 73.76259571198044), (18.551935138573278, 73.76261851075698), (18.551778754472185, 73.76266410831018), (18.55186457503151, 73.76250988129179), (18.551563249316903, 73.76234224322809), (18.551783204426403, 73.76194326463678), (18.55187665347968, 73.76196472230913), (18.552043208804424, 73.76202909532587), (18.55205592294446, 73.76203110698265), (18.552205314019034, 73.76204317692324), (18.552249,73.762305)],
                "capacity": 100
            }
        }
    },
"Delhi": {
    "center": (28.421240, 76.999859),
    "zoom": 18,
    "yard_name": "Delhi-Honda Sector35",
    "fleet": "Delhi GoMyGPS",

    "yard_boundary": [
        (28.421398, 76.999548),
        (28.421384, 76.999690),
        (28.421592, 76.999722),
        (28.421604, 77.000280),
        (28.421533, 77.000776),
        (28.421474, 77.000846),
        (28.420566, 77.000892),
        (28.420570, 77.000028),
        (28.420679, 77.000055),
        (28.420733, 76.999757),
        (28.420846, 76.999317),
        (28.421108, 76.999374),
        (28.421219, 76.999052),
        (28.421366, 76.999276)
    ],

    "gate": [
        (28.421427, 76.999205),
        (28.421366, 76.999276)
    ],

    "zones": {
        "RTL area": {
            "polygon": [
                (28.421365, 76.999202),
                (28.421271, 76.999062),
                (28.421250, 76.999469),
                (28.421385, 76.999310)
            ],
            "capacity": 35
        },

        "Rtl yard main": {
            "polygon": [
                (28.4206403, 77.0001324), 
                (28.4206778, 77.000726),
                (28.4215737, 77.0007858),
                (28.4214254, 77.0005897),
                (28.4212587, 77.0004698),
                (28.4213476, 77.0003999),
                (28.421191, 77.000219),


            ],
            "capacity": 250
        },

        "Rtl yard 1.0": {
            "polygon": [
                (28.419415, 76.999036), 
                (28.419440, 76.997942), 
                (28.420066, 76.998239), 
                (28.419962, 76.999042),


            ],
            "capacity": 150
        },

        "Rtl yard 2.0": {
                    "polygon": [
                        (28.421367, 77.007907), 
                        (28.420952, 77.007424), 
                        (28.420169, 77.008786), 
                        (28.420763, 77.009269)
        
        
                    ],
                    "capacity": 100
                },
    }
},
"Hyderabad": {
        # No center / yard_boundary / gate yet: the center and an
        # estimated boundary are computed from the zone corners at
        # startup (see _finalize_hubs). Replace with surveyed points.
        "zoom": 18,
        "yard_name": "HYD",
        "fleet": "Hyderabad GoMyGPS",

        "Entrance Area": [(17.5310278, 78.3572914),
                          (17.5310558, 78.3572992),
                          (17.5310848, 78.3571903),
                          (17.5310873, 78.3571677)],

#        "gate": [
 #           (19.0834834, 73.0301655),
  #          (19.083387,73.030316)
   #     ],

        "zones": {
            "Drop off zone": {
                "polygon": [(17.530757299999998, 78.3574031),
                            (17.5306909, 78.3572783),
                            (17.5307555, 78.3572775),
                            (17.530865, 78.3573115) 
                            ],
                            "capacity": 35
            },
            "OWN NOW Zone": {
                "polygon": [(17.5309956, 78.3573397),
                            (17.530954, 78.357283),
                            (17.5307374, 78.3572049),
                            (17.5307482, 78.3571622) 
                            ],
                            "capacity": 350
            },
            "Garage": {
                "polygon": [(17.530925, 78.357956),
                            (17.5307664, 78.3577253),
                            (17.5305393, 78.3574654),
                            (17.5307191, 78.3574747) 
                            ],
                            "capacity": 45
            },
            "Fi Zone": {
                            "polygon": [(17.5309933, 78.3572933),
                                        (17.5308957, 78.3576436),
                                        (17.5307919, 78.357434),
                                        (17.530953, 78.3573378) 
                                        ],
                                        "capacity": 45
                        },
            "Repair Zone": {
                "polygon": [(17.5310045, 78.3573997),
                            (17.5312987, 78.3575497),
                            (17.5310047, 78.3581931),
                            (17.530922, 78.3579628) 
                            ],
                            "capacity": 45
            },            
            "RTA Zone": {
                "polygon": [(17.530675199999997, 78.3573859),
                            (17.530252, 78.3574251),
                            (17.5302747, 78.3574116),
                            (17.530317399999998, 78.3573985) 
                            ],
                            "capacity": 35
            },
        }
    },

    # ----------------------------------------------------------
    # Hubs below come from "GPS & City Coordinates - City-wise Per
    # Hub coordinates" sheet. They have only a yard outline (no zones,
    # capacities or gate unless given); center is computed automatically.
    # ----------------------------------------------------------
    "Mumbai-Thane": {
        "zoom": 19,
        "yard_name": "Thane",
        "fleet": "Mumbai GoMyGPS",
        "yard_boundary": [
            (19.2037036, 72.96454709999999),
            (19.2034615, 72.9648006),
            (19.2035404, 72.9645805),
            (19.203411, 72.9644212),
        ],
        "zones": {},
    },
    "Mumbai-Belapur": {
        "zoom": 18,
        "yard_name": "Belapur",
        "fleet": "Mumbai GoMyGPS",
        "yard_boundary": [
            (19.008946, 73.032360),
            (19.009301, 73.033264),
            (19.008946, 73.033426),
            (19.008560, 73.032449),
        ],
        "zones": {},
    },
    "Kolkata": {
        "zoom": 18,
        "yard_name": "Kolkata",
        "fleet": "Kolkata GoMyGPS",
        "yard_boundary": [
            (22.511621, 88.314753),
            (22.511984, 88.314811),
            (22.511892, 88.315432),
            (22.511459, 88.315407),
        ],
        "zones": {},
    },
    "Banglore-Begur Parking": {
        "zoom": 18,
        "yard_name": "Begur Parking",
        "fleet": "Banglore GoMyGPS",
        # Reordered from the sheet (sheet order 1,2,3,4 -> 3,1,2,4):
        # the sheet's order made the outline cross over itself.
        "yard_boundary": [
            (12.8794763, 77.6306133),
            (12.8796391, 77.6320251),
            (12.8799100, 77.6321716),
            (12.8798251, 77.6304926),
        ],
        "zones": {},
    },
    "Banglore-HQ Parking": {
        "zoom": 18,
        "yard_name": "HQ Parking",
        "fleet": "Banglore GoMyGPS",
        "yard_boundary": [
            (12.878815, 77.643918),
            (12.878495, 77.643710),
            (12.878162, 77.644649),
            (12.878438, 77.644720),
        ],
        "zones": {},
    },
    "Chennai-Vanagaram": {
        "zoom": 18,
        "yard_name": "Yard-Vanagaram",
        "fleet": "Chennai GoMyGPS",
        "yard_boundary": [
            (13.066847, 80.151313),
            (13.066778, 80.151284),
            (13.066741, 80.151488),
            (13.065411, 80.151265),
            (13.065588, 80.150640),
            (13.065902, 80.150234),
            (13.066881, 80.150531),
            (13.066738, 80.151169),
            (13.066887, 80.151251),
        ],
        "gate": [
            (13.066847, 80.151313),
            (13.066887, 80.151251),
        ],
        "zones": {},
    },
    "Chennai-Gangai Amman Koli St": {
        "zoom": 18,
        "yard_name": "Yard-Gangai Amman Koli St",
        "fleet": "Chennai GoMyGPS",
        "yard_boundary": [
            (13.063446, 80.139508),
            (13.063272, 80.141285),
            (13.063894, 80.141374),
            (13.063810, 80.140491),
            (13.063984, 80.139626),
        ],
        "zones": {},
    },

    # ----------------------------------------------------------
    # ADD OTHER HUBS HERE
    #
    # "Pune": {
    #     "center": (LAT, LON),
    #     "zoom": 18,
    #     "yard_name": "Pune Yard",
    #     "yard_boundary": [(LAT,LON), ...],
    #     "gate": [(LAT,LON), (LAT,LON)],
    #     "zones": {
    #         "Driver Waiting": {"polygon": [...], "capacity": 35},
    #         "RTA Parking": {"polygon": [...], "capacity": 20},
    #         "Repair Parking": {"polygon": [...], "capacity": 45},
    #         "Pune Yard": {"polygon": [...], "capacity": 100}
    #     }
    # }
}

GPS_BOUNDARY_METERS = 15.0

# Vehicles further than this from the yard are not drawn on the map by
# default (a sidebar tick box shows them). Keeps the map fast.
NEAR_YARD_METERS = 1000.0

FLEET_TO_CITY = {
    "Mumbai GoMyGPS": "Mumbai",
    "Pune GoMyGPS": "Pune",
    "Delhi GoMyGPS": "Delhi",
    "Banglore GoMyGPS": "Banglore",
    "Kolkata GoMyGPS": "Kolkata",
    "Chennai GoMyGPS": "Chennai",
    "Hyderabad GoMyGPS": "Hyderabad",
}

FLEET_OPTIONS = list(FLEET_TO_CITY) + ["MapMyIndia – Pan India"]

UNZONED = 'Unzoned (inside yard)'

ZONE_PALETTE = ['#a855f7', '#f59e0b', '#2196f3', '#ec4899', '#14b8a6', '#84cc16', '#f97316']


def convex_hull(points):
    """Convex hull of (lat, lon) points (monotone chain)."""
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _finalize_hubs(hubs):
    """Fill in anything a hub config is missing so the app never crashes on it."""
    for hub in hubs.values():
        hub.setdefault('zones', {})
        if not hub.get('yard_boundary'):
            pts = [pt for cfg in hub['zones'].values() for pt in cfg['polygon']]
            pts += list(hub.get('Entrance Area', []))
            hub['yard_boundary'] = convex_hull(pts)
            hub['boundary_estimated'] = True
        if not hub.get('center'):
            b = hub['yard_boundary']
            hub['center'] = (sum(p[0] for p in b) / len(b), sum(p[1] for p in b) / len(b))
        hub.setdefault('gate', [])


_finalize_hubs(HUBS)

# ============================================================
# PARKING HOTSPOTS / REFERENCE POINTS
# These are physical GPS points collected from the parking area.
# They are used as reference points, not as exact parking-slot
# assignments. When a vehicle is searched, the nearest point is
# highlighted and the distance from the vehicle is shown.
# ============================================================
PARKING_HOTSPOTS = {
    "Mumbai": [
        # Line 1
        {"line": "Line 1", "point": "P1", "lat": 19.0855282, "lon": 73.0305254},
        {"line": "Line 1", "point": "P2", "lat": 19.0856865, "lon": 73.0305500},
        {"line": "Line 1", "point": "P3", "lat": 19.0858944, "lon": 73.0306081},
        {"line": "Line 1", "point": "P4", "lat": 19.0861120, "lon": 73.0307120},
        {"line": "Line 1", "point": "P5", "lat": 19.0863470, "lon": 73.0307771},

        # Line 2
        {"line": "Line 2", "point": "P1", "lat": 19.0863889, "lon": 73.0308871},
        {"line": "Line 2", "point": "P2", "lat": 19.0862518, "lon": 73.0308143},
        {"line": "Line 2", "point": "P3", "lat": 19.0860182, "lon": 73.0307368},
        {"line": "Line 2", "point": "P4", "lat": 19.0859330, "lon": 73.0307040},
        {"line": "Line 2", "point": "P5", "lat": 19.0856836, "lon": 73.0306653},

        # Line 3
        {"line": "Line 3", "point": "P1", "lat": 19.0854722, "lon": 73.0306812},
        {"line": "Line 3", "point": "P2", "lat": 19.0856195, "lon": 73.0307052},
        {"line": "Line 3", "point": "P3", "lat": 19.0856694, "lon": 73.0307564},
        {"line": "Line 3", "point": "P4", "lat": 19.0859487, "lon": 73.0308045},
        {"line": "Line 3", "point": "P5", "lat": 19.0859988, "lon": 73.0308376},
        {"line": "Line 3", "point": "P6", "lat": 19.0864150, "lon": 73.0309798},

        # Line 4
        {"line": "Line 4", "point": "P1", "lat": 19.0864146, "lon": 73.0309965},
        {"line": "Line 4", "point": "P2", "lat": 19.0863749, "lon": 73.0310138},
        {"line": "Line 4", "point": "P3", "lat": 19.0862132, "lon": 73.0310111},
        {"line": "Line 4", "point": "P4", "lat": 19.0859826, "lon": 73.0309409},
        {"line": "Line 4", "point": "P5", "lat": 19.0855267, "lon": 73.0307991},
        {"line": "Line 4", "point": "P6", "lat": 19.0854651, "lon": 73.0307923},

        # Line 5
        {"line": "Line 5", "point": "P1", "lat": 19.0854623, "lon": 73.0308248},
        {"line": "Line 5", "point": "P2", "lat": 19.0856269, "lon": 73.0309516},
        {"line": "Line 5", "point": "P3", "lat": 19.0857484, "lon": 73.0309484},
        {"line": "Line 5", "point": "P4", "lat": 19.0859275, "lon": 73.0310790},
        {"line": "Line 5", "point": "P5", "lat": 19.0861198, "lon": 73.0311204},
    ],
    # Add Pune parking points later in the same format:
    # "Pune": [{"line": "Line 1", "point": "P1", "lat": ..., "lon": ...}],
}

@st.cache_data(show_spinner=False)
def load_gps_file(path):
    sheets = pd.ExcelFile(path).sheet_names
    sheet = 'Summary Report' if 'Summary Report' in sheets else (
        'Summary' if 'Summary' in sheets else sheets[0]
    )
    df = pd.read_excel(path, sheet_name=sheet, header=5)

    required = ['Vehicle Number', 'Current Known Latitude', 'Current Known Longitude']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"Required GPS columns missing: {missing}. Available: {list(df.columns)}"
        )

    for c in ['Current Known Latitude', 'Current Known Longitude']:
        df[c] = pd.to_numeric(df[c], errors='coerce')

    df = df.dropna(
        subset=['Current Known Latitude', 'Current Known Longitude']
    ).copy()

    return df[
        df['Current Known Latitude'].between(-90, 90)
        & df['Current Known Longitude'].between(-180, 180)
    ].copy()


def find_latest_gps_file():
    candidates = []
    for folder in ['data', '.']:
        if os.path.isdir(folder):
            for f in os.listdir(folder):
                if f.lower().endswith(('.xlsx', '.xls')):
                    p = os.path.join(folder, f)
                    if os.path.isfile(p):
                        candidates.append(p)
    return max(candidates, key=os.path.getmtime) if candidates else None


def redact_secrets(text):
    """Hide access tokens / bearer tokens that appear in error messages."""
    text = re.sub(r'(?i)(accessToken=)[^&\s\'")]+', r'\1***', str(text))
    return re.sub(r'(?i)(bearer\s+)[^\s\'"]+', r'\1***', text)


# ------------------------------------------------------------
# GPS API calls happen ONLY on first load of a fleet or when
# "Refresh GPS now" is clicked. Results (including failures) are
# cached with no expiry and shared by everyone viewing the app,
# so changing filters, searching or switching hubs never hits the API.
# ------------------------------------------------------------
@st.cache_data(show_spinner="Fetching live GPS…")
def fetch_cng_vehicles(city):
    fetched_at = time.time()
    try:
        response = requests.get(
            st.secrets["CNG"]["URL"],
            params={"accessToken": st.secrets["CNG"]["TOKENS"][city]},
            timeout=15
        )
        response.raise_for_status()
        result = response.json()
        vehicles = (result.get("object") or []) if isinstance(result, dict) else []
        return {"vehicles": vehicles, "error": None, "fetched_at": fetched_at}
    except Exception as e:
        return {"vehicles": [], "error": redact_secrets(f"CNG GPS API failed for {city}: {e}"),
                "fetched_at": fetched_at}


@st.cache_data(show_spinner="Fetching live GPS…")
def fetch_ev_vehicles():
    fetched_at = time.time()
    try:
        ev_config = st.secrets.get("EV", {})
        ev_url = ev_config.get("URL")
        ev_token = ev_config.get("TOKEN")
        if not ev_url or not ev_token:
            raise ValueError("EV URL/TOKEN missing in secrets")

        response = requests.get(
            ev_url,
            headers={"Authorization": f"Bearer {ev_token}", "Accept": "application/json"},
            timeout=20
        )
        response.raise_for_status()
        result = response.json()
        if isinstance(result, list):
            vehicles = result
        elif isinstance(result, dict):
            vehicles = result.get("devices") or result.get("data") or result.get("object") or []
        else:
            vehicles = []
        return {"vehicles": vehicles, "error": None, "fetched_at": fetched_at}
    except Exception as e:
        return {"vehicles": [], "error": redact_secrets(f"EV GPS API skipped/failed: {e}"),
                "fetched_at": fetched_at}


def clear_gps_cache():
    fetch_cng_vehicles.clear()
    fetch_ev_vehicles.clear()


def get_live_gps_data(selected_fleet):
    """
    Fetch live GPS data from:
    - CNG: Track7 / MilliTrek with city-wise tokens
    - EV: Mappls with one common India-wide token
    Returns: dataframe, list of warning messages, fetch time (epoch seconds)
    """

    all_rows = []
    warnings = []
    fetched_at = None

    # ============================================================
    # CNG - Track7 / MilliTrek
    # ============================================================

    if selected_fleet in FLEET_TO_CITY:

        city = FLEET_TO_CITY[selected_fleet]

        cng = fetch_cng_vehicles(city)
        fetched_at = cng["fetched_at"]
        if cng["error"]:
            warnings.append(cng["error"])

        try:
            for vehicle in cng["vehicles"]:

                attrs = vehicle.get("attributes") or {}

                ignition = vehicle.get("ignition")
                motion = vehicle.get("motion")

                if motion is True:
                    current_status = "Running"
                elif motion is False:
                    current_status = "Stopped"
                elif ignition is True:
                    current_status = "Ignition On"
                elif ignition is False:
                    current_status = "Ignition Off"
                else:
                    current_status = "Unknown"

                all_rows.append({
                    "Vehicle Number": vehicle.get("name"),
                    "Device ID": vehicle.get("deviceUniqueId"),
                    "Current Known Latitude": vehicle.get("latitude"),
                    "Current Known Longitude": vehicle.get("longitude"),
                    "Current Known Address": vehicle.get("address"),
                    "Current Status": current_status,
                    "Average speed": vehicle.get("speed"),
                    "Top speed": vehicle.get("speed"),
                    "Speed": vehicle.get("speed"),
                    "Timestamp": vehicle.get("timestamp"),
                    "GPS Valid": vehicle.get("valid"),
                    "Ignition": ignition,
                    "Motion": motion,
                    "Course": vehicle.get("course"),
                    "Accuracy": vehicle.get("accuracy"),
                    "Battery Level": attrs.get("batteryLevel"),
                    "Today Distance": vehicle.get("todayDistance"),
                    "Total Distance": vehicle.get("totalDistance"),
                    "City": city,
                    "Fuel Type": "CNG",
                })

        except Exception as e:
            warnings.append(redact_secrets(f"CNG GPS data for {city} could not be read: {e}"))

    # ============================================================
    # EV - Mappls
    # ============================================================

    # Run EV API only when MapMyIndia is selected
    if selected_fleet == "MapMyIndia – Pan India":

        ev = fetch_ev_vehicles()
        fetched_at = ev["fetched_at"]
        if ev["error"]:
            warnings.append(ev["error"])

        try:
            vehicles = ev["vehicles"]

            for vehicle in vehicles:

                device_details = vehicle.get("deviceDetails") or {}
                location = vehicle.get("location") or {}
                can_info = vehicle.get("canInfo") or {}

                vehicle_number = (
                    device_details.get("registrationNumber")
                    or vehicle.get("name")
                )

                latitude = location.get("latitude")
                longitude = location.get("longitude")
                speed = location.get("speedKph")
                timestamp = location.get("gpsTime")

                if speed is not None and speed > 0:
                    current_status = "Running"
                else:
                    current_status = "Stopped"

                all_rows.append({
                    "Vehicle Number": vehicle_number,
                    "Device ID": (
                        vehicle.get("id")
                        or device_details.get("trackingCode")
                    ),
                    "Current Known Latitude": latitude,
                    "Current Known Longitude": longitude,
                    "Current Known Address": location.get("address"),
                    "Current Status": current_status,
                    "Average speed": speed,
                    "Top speed": speed,
                    "Speed": speed,
                    "Timestamp": timestamp,
                    "GPS Valid": (
                        latitude is not None
                        and longitude is not None
                    ),
                    "Ignition": None,
                    "Motion": None,
                    "Course": location.get("heading"),
                    "Accuracy": location.get("gpsSignal"),
                    "Battery Level": can_info.get("stateOfCharge"),
                    "Today Distance": None,
                    "Total Distance": location.get("odometer"),
                    "City": "Pan India",
                    "Fuel Type": "EV",
                })

        except Exception as e:
            warnings.append(redact_secrets(f"EV GPS data could not be read: {e}"))

    # ============================================================
    # Final combined dataframe
    # ============================================================

    if not all_rows:
        return pd.DataFrame(), warnings, fetched_at

    df = pd.DataFrame(all_rows)

    # Remove invalid GPS coordinates
    df = df[
        df["Current Known Latitude"].notna()
        & df["Current Known Longitude"].notna()
        & (df["Current Known Latitude"] != 0)
        & (df["Current Known Longitude"] != 0)
        & df["Current Known Latitude"].between(-90, 90)
        & df["Current Known Longitude"].between(-180, 180)
    ].copy()

    return df, warnings, fetched_at


def get_gps_source(selected_fleet):
    """
    Prefer live GPS API.
    If the API is unavailable, use the latest Excel backup only
    when it can be safely matched to the selected fleet.
    Returns: dataframe, source label, source detail, error message,
             API warnings, API fetch time (epoch seconds or None)
    """
    try:
        live_df, warnings, fetched_at = get_live_gps_data(selected_fleet)

        if not live_df.empty:
            return (
                live_df,
                "LIVE API",
                f"{selected_fleet} • {len(live_df):,} GPS positions",
                None,
                warnings,
                fetched_at,
            )

        api_error = "; ".join(warnings) or "Live GPS API returned no valid vehicle positions."

    except Exception as e:
        warnings, fetched_at = [], None
        api_error = redact_secrets(f"{type(e).__name__}: {e}")

    return (*_excel_fallback(selected_fleet, api_error), warnings, fetched_at)


def _excel_fallback(selected_fleet, api_error):
    """Excel backup used when the live API gave nothing. Returns 4 values."""

    # Do not use a CNG Excel file as backup for Pan-India EV data.
    if selected_fleet == "MapMyIndia – Pan India":
        return (
            pd.DataFrame(),
            "ERROR",
            "",
            f"Live MapMyIndia API unavailable. Excel backup not used for Pan-India EV data. "
            f"API error: {api_error}"
        )

    file_path = find_latest_gps_file()

    if not file_path:
        return (
            pd.DataFrame(),
            "ERROR",
            "",
            f"Live API: {api_error} | No Excel backup found."
        )

    try:
        excel_df = load_gps_file(file_path)

        if excel_df.empty:
            return (
                pd.DataFrame(),
                "ERROR",
                "",
                f"Live API: {api_error} | Excel backup is empty."
            )

        # Match selected CNG fleet to city.
        selected_city = FLEET_TO_CITY.get(selected_fleet)

        # Only use the Excel file if it contains a City column.
        if "City" not in excel_df.columns:
            return (
                pd.DataFrame(),
                "ERROR",
                "",
                f"Live API: {api_error} | Excel backup cannot be safely matched "
                f"to {selected_city}; City column is missing."
            )

        # Filter Excel data to selected city.
        excel_df["City"] = excel_df["City"].astype(str).str.strip()

        filtered_df = excel_df[
            excel_df["City"].str.lower() == selected_city.lower()
        ].copy()

        if filtered_df.empty:
            return (
                pd.DataFrame(),
                "ERROR",
                "",
                f"Live API: {api_error} | Excel backup contains no data "
                f"for {selected_city}."
            )

        return (
            filtered_df,
            "EXCEL BACKUP",
            f"{os.path.basename(file_path)} • {len(filtered_df):,} {selected_city} GPS positions",
            api_error
        )

    except Exception as e:
        return (
            pd.DataFrame(),
            "ERROR",
            "",
            f"Live API: {api_error} | Excel: {type(e).__name__}: {e}"
        )

def point_inside_polygon(lat,lon,polygon):
    inside=False; j=len(polygon)-1
    for i in range(len(polygon)):
        lat_i,lon_i=polygon[i]; lat_j,lon_j=polygon[j]
        if ((lon_i>lon)!=(lon_j>lon)):
            d=lon_j-lon_i if abs(lon_j-lon_i)>1e-12 else 1e-12
            intersection=(lat_j-lat_i)*(lon-lon_i)/d+lat_i
            if lat<intersection: inside=not inside
        j=i
    return inside

def distance_to_segment_m(lat,lon,p1,p2):
    mx=111320.0*math.cos(math.radians(lat)); my=111320.0
    px=(lon-p1[1])*mx; py=(lat-p1[0])*my
    sx=(p2[1]-p1[1])*mx; sy=(p2[0]-p1[0])*my
    q=sx*sx+sy*sy
    if q<=1e-12: return math.hypot(px,py)
    t=max(0,min(1,(px*sx+py*sy)/q))
    return math.hypot(px-t*sx,py-t*sy)

def distance_to_polygon_m(lat,lon,polygon):
    return min(distance_to_segment_m(lat,lon,polygon[i],polygon[(i+1)%len(polygon)]) for i in range(len(polygon)))

def geofence_status(lat,lon,hub):
    # Zones count as part of the yard, so satellite yards that sit outside
    # the main boundary (e.g. Delhi "Rtl yard 1.0/2.0", Vasai "Stock Yard")
    # are not reported as "Confirmed Outside".
    areas = [hub['yard_boundary']] + [cfg['polygon'] for cfg in hub['zones'].values()]
    d = min(distance_to_polygon_m(lat,lon,a) for a in areas)
    if any(point_inside_polygon(lat,lon,a) for a in areas):
        return 'Inside Yard', d
    if d <= GPS_BOUNDARY_METERS:
        return 'Boundary / GPS Uncertainty', d
    return 'Confirmed Outside', d

def get_zone(lat,lon,hub):
    # A zone named like the whole yard (e.g. Pune "PUNE") is a catch-all,
    # so it is always checked last regardless of its order in HUBS.
    zones = sorted(hub['zones'].items(), key=lambda kv: kv[0] == hub['yard_name'])
    for zone,cfg in zones:
        if point_inside_polygon(lat,lon,cfg['polygon']):
            return zone
    if point_inside_polygon(lat,lon,hub['yard_boundary']):
        return UNZONED
    return 'Outside Yard'

# ============================================================
# 15 m x 15 m GRID ZONES
# Each hub is covered by a north-up grid of square cells, GRID_CELL_M
# on each side, laid over the yard boundary and all named zones.
# Rows are letters from north to south (A, B, ... Z, AA, AB ...),
# columns are numbers from west to east (1, 2, 3 ...), so a cell is
# named like "A1" or "C4". Only cells that touch the yard are kept;
# column numbers stay absolute, so neighbouring names always line up.
# ============================================================
GRID_CELL_M = 15.0
OUTSIDE_GRID = 'Outside Grid'
_GRID_CACHE = {}


def grid_row_label(index):
    """0 -> A, 25 -> Z, 26 -> AA, 27 -> AB ..."""
    label = ''
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        label = chr(65 + rem) + label
    return label


def _cell_touches_yard(north, south, west, east, areas):
    # A cell counts if any sample point in it is inside a yard area,
    # or any yard corner falls inside the cell.
    steps = [i / 4 for i in range(5)]
    for fy in steps:
        for fx in steps:
            lat = north - (north - south) * fy
            lon = west + (east - west) * fx
            if any(point_inside_polygon(lat, lon, a) for a in areas):
                return True
    return any(south <= p[0] <= north and west <= p[1] <= east for a in areas for p in a)


def get_hub_grid(hub_name):
    """Build (once per hub) the grid of 15 m cells covering the yard."""
    if hub_name in _GRID_CACHE:
        return _GRID_CACHE[hub_name]

    hub = HUBS[hub_name]
    areas = [hub['yard_boundary']] + [cfg['polygon'] for cfg in hub['zones'].values()]
    lats = [p[0] for a in areas for p in a]
    lons = [p[1] for a in areas for p in a]
    north, south, west, east = max(lats), min(lats), min(lons), max(lons)

    lat0 = (north + south) / 2
    dlat = GRID_CELL_M / 111320.0
    dlon = GRID_CELL_M / (111320.0 * math.cos(math.radians(lat0)))
    rows = max(1, math.ceil((north - south) / dlat))
    cols = max(1, math.ceil((east - west) / dlon))

    cells = {}
    for r in range(rows):
        for c in range(cols):
            n = north - r * dlat
            s = n - dlat
            w = west + c * dlon
            e = w + dlon
            if _cell_touches_yard(n, s, w, e, areas):
                cells[f"{grid_row_label(r)}{c + 1}"] = {
                    'row': r, 'col': c,
                    'bounds': [(s, w), (n, e)],
                    'center': ((n + s) / 2, (w + e) / 2),
                }

    grid = {'north': north, 'west': west, 'dlat': dlat, 'dlon': dlon,
            'rows': rows, 'cols': cols, 'cells': cells}
    _GRID_CACHE[hub_name] = grid
    return grid


def get_grid_cell(lat, lon, grid):
    r = math.floor((grid['north'] - lat) / grid['dlat'])
    c = math.floor((lon - grid['west']) / grid['dlon'])
    if r < 0 or c < 0:
        return OUTSIDE_GRID
    name = f"{grid_row_label(r)}{c + 1}"
    return name if name in grid['cells'] else OUTSIDE_GRID


def sorted_grid_cells(grid):
    return sorted(grid['cells'], key=lambda n: (grid['cells'][n]['row'], grid['cells'][n]['col']))


def add_grid_layer(m, grid, counts):
    """Draw grid cells (shaded by vehicle count) and their labels."""
    cells_layer = folium.FeatureGroup(name=f'Grid zones ({GRID_CELL_M:.0f} m)', show=True)
    labels_layer = folium.FeatureGroup(name='Grid labels', show=True)
    peak = max(counts.values()) if counts else 0

    for name in sorted_grid_cells(grid):
        cell = grid['cells'][name]
        n = int(counts.get(name, 0))
        opacity = 0.0 if n == 0 else 0.15 + 0.45 * (n / peak if peak else 0)
        folium.Rectangle(
            bounds=cell['bounds'],
            color='#0ea5e9',
            weight=1,
            fill=True,
            fill_color='#0284c7',
            fill_opacity=opacity,
            tooltip=f"Grid {name} • {n} vehicle{'s' if n != 1 else ''}",
        ).add_to(cells_layer)
        folium.Marker(
            cell['center'],
            icon=folium.DivIcon(
                icon_size=(36, 14), icon_anchor=(18, 7),
                html=(f"<div style='text-align:center;font:700 10px Arial;color:#0f172a;"
                      f"text-shadow:0 0 3px #fff,0 0 3px #fff'>{name}</div>")
            ),
        ).add_to(labels_layer)

    cells_layer.add_to(m)
    labels_layer.add_to(m)

def haversine_distance_m(lat1, lon1, lat2, lon2):
    """Great-circle distance between two GPS coordinates in metres."""
    r = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def get_nearest_hotspot(lat, lon, hub_name):
    """Return the nearest physical parking reference point for a vehicle."""
    points = PARKING_HOTSPOTS.get(hub_name, [])
    if not points:
        return None

    nearest = None
    nearest_distance = float('inf')
    for point in points:
        distance = haversine_distance_m(lat, lon, point['lat'], point['lon'])
        if distance < nearest_distance:
            nearest_distance = distance
            nearest = dict(point)
            nearest['distance_m'] = distance
    return nearest


def hotspot_popup(point, selected_vehicle=None):
    title = f"📍 {point['line']} — {point['point']}"
    extra = ''
    if selected_vehicle:
        extra = (
            f"<hr style='margin:7px 0'><b>Vehicle:</b> {selected_vehicle}"
            f"<br><b>Distance:</b> {point['distance_m']:.1f} m"
        )
    return (
        f"<div style='width:230px;font-family:Arial;line-height:1.5'>"
        f"<div style='font-size:16px;font-weight:800'>{title}</div>"
        f"<b>GPS:</b> {point['lat']:.7f}, {point['lon']:.7f}"
        f"{extra}</div>"
    )


def add_hotspot_markers(m, hub_name, selected_hotspot=None):
    """Add all physical parking reference points and emphasize the selected one."""
    points = PARKING_HOTSPOTS.get(hub_name, [])
    if not points:
        return

    layer = folium.FeatureGroup(name='Parking Hotspots', show=True)
    for point in points:
        is_selected = (
            selected_hotspot is not None
            and point['line'] == selected_hotspot['line']
            and point['point'] == selected_hotspot['point']
        )
        if is_selected:
            folium.CircleMarker(
                [point['lat'], point['lon']], radius=12, color='white', weight=3,
                fill=True, fill_color='#7c3aed', fill_opacity=.98,
                tooltip=f"📍 NEAREST: {point['line']} — {point['point']}",
                popup=folium.Popup(hotspot_popup(selected_hotspot), max_width=280)
            ).add_to(layer)
            folium.Marker(
                [point['lat'], point['lon']],
                icon=folium.DivIcon(
                    html="<div style='transform:translate(-50%,-145%);background:#7c3aed;color:white;border:2px solid white;border-radius:8px;padding:4px 7px;font:800 11px Arial;white-space:nowrap'>📍 NEAREST HOTSPOT</div>"
                )
            ).add_to(layer)
        else:
            folium.CircleMarker(
                [point['lat'], point['lon']], radius=4.5, color='white', weight=1,
                fill=True, fill_color='#7c3aed', fill_opacity=.8,
                tooltip=f"📍 {point['line']} — {point['point']}",
                popup=folium.Popup(hotspot_popup(point), max_width=280)
            ).add_to(layer)
    layer.add_to(m)


@st.cache_data(show_spinner=False, max_entries=64)
def classify_vehicles(_df, hub_name, data_key):
    """
    Add Detected Zone, Geofence Status, Fence Distance (m) and Grid Zone.
    `_df` is not hashed (leading underscore); `data_key` identifies the
    GPS fetch, so a new fetch or another hub gives a new result.
    """
    hub = HUBS[hub_name]
    grid = get_hub_grid(hub_name)
    out = _df.copy()
    zones, statuses, distances, cells = [], [], [], []
    for lat, lon in zip(out['Current Known Latitude'].astype(float), out['Current Known Longitude'].astype(float)):
        status, dist = geofence_status(lat, lon, hub)
        zones.append('Boundary / GPS Uncertainty' if status == 'Boundary / GPS Uncertainty'
                     else get_zone(lat, lon, hub))
        statuses.append(status)
        distances.append(round(dist, 1))
        cells.append(get_grid_cell(lat, lon, grid))
    out['Detected Zone'] = zones
    out['Geofence Status'] = statuses
    out['Fence Distance (m)'] = distances
    out['Grid Zone'] = cells
    return out


# One JS function draws every vehicle marker in the browser. Python only
# sends a compact list of values per vehicle; the popup HTML is built on
# click, and all text is HTML-escaped.
VEHICLE_MARKER_JS = """
function (row) {
    function esc(s) {
        return String(s).replace(/[&<>"']/g, function (c) {
            return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c];
        });
    }
    var m = L.circleMarker(new L.LatLng(row[0], row[1]), {
        radius: 5.5, color: 'white', weight: 1.2,
        fill: true, fillColor: row[2], fillOpacity: 0.95
    });
    m.bindTooltip('🚗 ' + esc(row[3]) + ' • ' + esc(row[4]) + ' • ' + esc(row[5]));
    m.bindPopup(function () {
        return '<div style="width:270px;font-family:Arial;line-height:1.5">'
            + '<div style="font-size:17px;font-weight:800;margin-bottom:7px">🚗 ' + esc(row[3]) + '</div>'
            + '<b>Grid zone:</b> ' + esc(row[4]) + '<br>'
            + '<b>Area:</b> ' + esc(row[5]) + '<br>'
            + '<b>GPS status:</b> ' + esc(row[6]) + '<br>'
            + '<b>Fence distance:</b> ' + esc(row[7]) + ' m<br>'
            + '<b>Status:</b> ' + esc(row[8]) + '<br>'
            + '<b>Avg speed:</b> ' + esc(row[9])
            + '<hr style="margin:7px 0"><b>GPS position</b><br>'
            + Number(row[0]).toFixed(6) + ', ' + Number(row[1]).toFixed(6) + '<br>'
            + '<span style="font-size:11px;color:#666">' + esc(row[10]) + '</span></div>';
    }, {maxWidth: 320});
    return m;
}
"""


def _cell(value):
    return '-' if value is None or (isinstance(value, float) and math.isnan(value)) else str(value)


def add_vehicle_layer(m, vehicles):
    """All vehicle markers as one fast, clustered layer."""
    data = [
        [float(r['Current Known Latitude']), float(r['Current Known Longitude']), marker_fill(r),
         _cell(r.get('Vehicle Number')), _cell(r.get('Grid Zone')), _cell(r.get('Detected Zone')),
         _cell(r.get('Geofence Status')), _cell(r.get('Fence Distance (m)')), _cell(r.get('Current Status')),
         _cell(r.get('Average speed')), _cell(r.get('Current Known Address'))]
        for r in vehicles.to_dict('records')
    ]
    FastMarkerCluster(
        data, callback=VEHICLE_MARKER_JS, name='GPS Vehicles',
        options={'spiderfyOnMaxZoom': True, 'showCoverageOnHover': False, 'zoomToBoundsOnClick': True,
                 'disableClusteringAtZoom': 19, 'maxClusterRadius': 35},
    ).add_to(m)


def marker_fill(row):
    g=row.get('Geofence Status','')
    s=str(row.get('Current Status','')).lower()
    if g=='Confirmed Outside': return '#ef4444'
    if g=='Boundary / GPS Uncertainty': return '#facc15'
    if 'running' in s: return '#22c55e'
    if 'stop' in s or 'idle' in s: return '#f59e0b'
    return '#60a5fa'

def popup_html(row):
    v=str(row['Vehicle Number']); z=str(row.get('Detected Zone','-')); status=str(row.get('Current Status','-'))
    lat=float(row['Current Known Latitude']); lon=float(row['Current Known Longitude'])
    return f'''<div style="width:270px;font-family:Arial;line-height:1.5"><div style="font-size:17px;font-weight:800;margin-bottom:7px">🚗 {v}</div><b>Grid zone:</b> {row.get('Grid Zone','-')}<br><b>Area:</b> {z}<br><b>GPS status:</b> {row.get('Geofence Status','-')}<br><b>Fence distance:</b> {row.get('Fence Distance (m)','-')} m<br><b>Status:</b> {status}<br><b>Avg speed:</b> {row.get('Average speed','-')}<hr style="margin:7px 0"><b>GPS position</b><br>{lat:.6f}, {lon:.6f}<br><span style="font-size:11px;color:#666">{str(row.get('Current Known Address','-'))}</span></div>'''

def add_marker(group,row,selected=False):
    lat=float(row['Current Known Latitude']); lon=float(row['Current Known Longitude']); v=str(row['Vehicle Number'])
    if selected:
        folium.CircleMarker([lat,lon],radius=14,color='white',weight=3,fill=True,fill_color='#ef4444',fill_opacity=.95,tooltip=f'📍 SELECTED: {v}',popup=folium.Popup(popup_html(row),max_width=320)).add_to(group)
        folium.Marker([lat,lon],icon=folium.DivIcon(html='<div style="transform:translate(-50%,-130%);background:#111827;color:white;border:2px solid white;border-radius:7px;padding:4px 7px;font:800 11px Arial;white-space:nowrap">📍 SELECTED</div>')).add_to(group)
    else:
        folium.CircleMarker([lat,lon],radius=5.5,color='white',weight=1.2,fill=True,fill_color=marker_fill(row),fill_opacity=.95,tooltip=f'🚗 {v} • {row.get("Grid Zone","-")} • {row.get("Detected Zone","-")}',popup=folium.Popup(popup_html(row),max_width=320)).add_to(group)

# Header
st.markdown('''<style>.main-title{font-size:30px;font-weight:800;color:#f8fafc}.sub-title{color:#94a3b8;font-size:14px;margin-bottom:18px}.kpi{background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:15px;min-height:100px}.kpi-label{font-size:11px;color:#64748b!important;font-weight:700}.kpi-value{font-size:30px;font-weight:850;color:#0f172a!important}.small{font-size:12px;color:#64748b!important}.zone-card{background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:14px;min-height:100px}.zone-name{font-size:13px;font-weight:800;color:#334155!important}.zone-count{font-size:23px;font-weight:850;color:#0f172a!important}.zone-note{font-size:12px;color:#64748b!important}.progress-bg{height:7px;background:#e2e8f0;border-radius:99px;margin-top:8px;overflow:hidden}</style><div class="main-title">🚗 Everest Fleet — Yard Control</div><div class="sub-title">Live GPS • yard geofencing • vehicle-level positioning</div>''',unsafe_allow_html=True)

# Hub selector
with st.sidebar:
    st.caption(f"Signed in as **{st.session_state['auth_user']}**")
    if st.button('Sign out', width='stretch'):
        st.session_state.pop('auth_user', None)
        st.rerun()

    st.header('Hub')

    selected_hub_name = st.selectbox(
        'Select hub',
        list(HUBS.keys()),
        index=0
    )

    hub = HUBS[selected_hub_name]

    st.header('Fleet')

    # Default the fleet to the hub's own fleet. The key is per hub, so
    # switching hub resets the fleet to the matching one.
    hub_fleet = hub.get('fleet')
    selected_fleet = st.selectbox(
        'Select fleet',
        FLEET_OPTIONS,
        index=FLEET_OPTIONS.index(hub_fleet) if hub_fleet in FLEET_OPTIONS else 0,
        key=f'fleet_for_{selected_hub_name}'
    )
    if hub_fleet and selected_fleet != hub_fleet:
        st.caption(f'⚠️ {selected_hub_name} normally uses {hub_fleet}.')

if hub.get('boundary_estimated'):
    st.warning(
        f"{selected_hub_name}: no surveyed yard boundary configured. Using an estimate "
        f"drawn around the zone corners — add `yard_boundary` and `gate` to HUBS."
    )

df, gps_source, gps_source_detail, gps_error, gps_warnings, gps_fetched_at = get_gps_source(selected_fleet)

for w in gps_warnings:
    if gps_source == "LIVE API":
        st.warning(w)
fetched_label = (
    time.strftime('%d %b %Y, %H:%M:%S', time.localtime(gps_fetched_at))
    if gps_fetched_at else "not fetched"
)

if df.empty:
    st.error("No GPS data could be loaded from Track7 or the Excel backup.")
    if gps_error:
        st.code(gps_error)
    st.stop()

# Live-source status banner.
if gps_source == "LIVE API":
    st.success(
        f"🟢 LIVE GPS • {gps_source_detail} • last fetched {fetched_label} "
        f"— click **↻ Refresh GPS now** in the sidebar for new positions"
    )
elif gps_source == "EXCEL BACKUP":
    st.warning(
        f"🟡 LIVE API UNAVAILABLE — using Excel backup: {gps_source_detail}"
    )
    if gps_error:
        with st.expander("Show API connection error"):
            st.code(gps_error)
else:
    st.error(gps_error or "GPS source unavailable.")
    st.stop()

# Zone / yard status / grid square for every vehicle. Computed once per
# GPS fetch and hub, then shared by every user and every click.
df = classify_vehicles(
    df, selected_hub_name,
    (selected_fleet, gps_source, gps_source_detail, gps_fetched_at)
)
hub_grid = get_hub_grid(selected_hub_name)
grid_counts = df.loc[df['Grid Zone'] != OUTSIDE_GRID, 'Grid Zone'].value_counts().to_dict()

with st.sidebar:
    st.header('Map Controls')
    show_outside=st.checkbox('Show confirmed outside vehicles',True)
    show_far=st.checkbox(
        f'Show vehicles more than {NEAR_YARD_METERS/1000:g} km from yard on map', False,
        help='Off = faster map. Far vehicles are still counted in the KPIs and listed in the table.'
    )
    show_boundary=st.checkbox('Show boundary / uncertain GPS',True)
    selected_zone=st.selectbox('Filter area',['All Zones']+list(hub['zones'])+[UNZONED,'Boundary / GPS Uncertainty','Confirmed Outside'])
    selected_grid=st.selectbox(
        'Filter grid zone',
        ['All grid zones']+sorted_grid_cells(hub_grid),
        key=f'grid_for_{selected_hub_name}'
    )
    search_vehicle=st.text_input('🔎 Search vehicle number',placeholder='e.g. MH01EF5521').strip().upper()
    # The GPS API is called only when this button is clicked (or the first
    # time a fleet is opened). There is no automatic refresh.
    if st.button('↻ Refresh GPS now', width='stretch'):
        clear_gps_cache()
        st.rerun()
    st.caption(f'Last API call: {fetched_label}')

    st.caption(f'Hub: {selected_hub_name}')
    st.caption(f'GPS source: {gps_source}')
    st.caption(gps_source_detail)

map_df=df.copy()
if selected_zone!='All Zones':
    map_df=map_df[map_df['Geofence Status']==selected_zone] if selected_zone in ['Boundary / GPS Uncertainty','Confirmed Outside'] else map_df[map_df['Detected Zone']==selected_zone]
if selected_grid!='All grid zones': map_df=map_df[map_df['Grid Zone']==selected_grid]
if search_vehicle: map_df=map_df[map_df['Vehicle Number'].astype(str).str.upper().str.contains(search_vehicle,na=False)]
if not show_outside: map_df=map_df[map_df['Geofence Status']!='Confirmed Outside']
if not show_boundary: map_df=map_df[map_df['Geofence Status']!='Boundary / GPS Uncertainty']

# Vehicles drawn on the map. Far-away vehicles are left off unless asked
# for (or searched), which keeps the map fast; the table still lists them.
map_vehicles = map_df if (show_far or search_vehicle) else map_df[map_df['Fence Distance (m)'] <= NEAR_YARD_METERS]
hidden_far = len(map_df) - len(map_vehicles)

selected_row=None
if search_vehicle:
    exact=df[df['Vehicle Number'].astype(str).str.upper()==search_vehicle]
    if not exact.empty: selected_row=exact.iloc[0]; st.success(f"Vehicle found: {search_vehicle} • Grid {selected_row['Grid Zone']} • {selected_row['Geofence Status']} • {selected_row['Detected Zone']}")

selected_hotspot = None
if selected_row is not None:
    selected_hotspot = get_nearest_hotspot(
        float(selected_row['Current Known Latitude']),
        float(selected_row['Current Known Longitude']),
        selected_hub_name
    )
    if selected_hotspot:
        st.info(
            f"📍 Nearest parking hotspot: **{selected_hotspot['line']} — {selected_hotspot['point']}**"
            f" • {selected_hotspot['distance_m']:.1f} m from vehicle"
        )

# KPIs
inside=int((df['Geofence Status']=='Inside Yard').sum()); boundary=int((df['Geofence Status']=='Boundary / GPS Uncertainty').sum()); outside=int((df['Geofence Status']=='Confirmed Outside').sum())
running=int(df['Current Status'].astype(str).str.contains('running',case=False,na=False).sum()) if 'Current Status' in df.columns else 0
cols=st.columns(6)
for c,(lab,val,note) in zip(cols,[('FLEET',len(df),'vehicles with GPS'),('GRID ZONES IN USE',len(grid_counts),f"of {len(hub_grid['cells'])} cells ({GRID_CELL_M:.0f} m)"),('IN YARD',inside,'inside fence / zones'),('BOUNDARY',boundary,f'within {GPS_BOUNDARY_METERS:.0f} m'),('OUTSIDE',outside,'confirmed outside'),('RUNNING',running,'currently running')]):
    with c: st.markdown(f'<div class="kpi"><div class="kpi-label">{lab}</div><div class="kpi-value">{val}</div><div class="small">{note}</div></div>',unsafe_allow_html=True)

# Zone cards
st.subheader(f'Zone Capacity — {selected_hub_name}')
zone_names=list(hub['zones'])
if not zone_names:
    st.caption(f"No zones configured for {selected_hub_name} yet — "
               f"{int((df['Detected Zone']==UNZONED).sum())} vehicles inside the yard outline.")
for start in range(0,len(zone_names),4):
  zcols=st.columns(4)
  for c,zone in zip(zcols,zone_names[start:start+4]):
    n=int((df['Detected Zone']==zone).sum()); cap=hub['zones'][zone]['capacity']; pct=min(n/cap,1) if cap else 0
    with c: st.markdown(f'<div class="zone-card"><div class="zone-name">{zone.upper()}</div><div><span class="zone-count">{n}</span><span class="zone-note"> / {cap}</span></div><div class="progress-bg"><div style="height:100%;width:{pct*100:.1f}%;background:#2563eb"></div></div><div class="zone-note">{pct:.0%} utilized</div></div>',unsafe_allow_html=True)

# Shared map layers
def add_base(m):
    folium.TileLayer(
        'OpenStreetMap',
        name='Street Map',
        control=True,
        max_zoom=22
    ).add_to(m)

    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri World Imagery',
        name='Satellite',
        control=True,
        max_zoom=22
    ).add_to(m)

    folium.TileLayer(
        tiles='https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png',
        attr='OpenStreetMap HOT',
        name='High Contrast',
        control=True,
        max_zoom=22
    ).add_to(m)

    folium.Polygon(
        hub['yard_boundary'],
        color='#00e676',
        weight=4,
        fill=True,
        fill_color='#00e676',
        fill_opacity=.07,
        tooltip=f"{selected_hub_name} — {hub['yard_name']}"
                + (" (estimated boundary)" if hub.get('boundary_estimated') else "")
    ).add_to(m)

    for i,(zone,cfg) in enumerate(hub['zones'].items()):
        if zone == hub['yard_name']:
            continue
        color = ZONE_PALETTE[i % len(ZONE_PALETTE)]
        n = int((df['Detected Zone']==zone).sum())
        folium.Polygon(
            cfg['polygon'],
            color=color,
            weight=3,
            fill=True,
            fill_color=color,
            fill_opacity=.22,
            tooltip=f'{zone} • {n}/{cfg["capacity"]}'
        ).add_to(m)

    if hub.get('Drive Passage'):
        folium.PolyLine(
            hub['Drive Passage'],
            color='#64748b',
            weight=5,
            dash_array='10,6',
            tooltip='DRIVE PASSAGE'
        ).add_to(m)

    if len(hub.get('gate', [])) >= 2:
        folium.PolyLine(
            hub['gate'],
            color='#ef4444',
            weight=7,
            tooltip='ENTRY / EXIT GATE'
        ).add_to(m)

    if hub.get('Entrance Area'):
        folium.Polygon(
            hub['Entrance Area'],
            color='#ef4444',
            weight=3,
            fill=True,
            fill_opacity=.25,
            tooltip='ENTRANCE AREA'
        ).add_to(m)

    # Reference ring around the physical fence. This is not a second yard.
    # It visualizes the GPS uncertainty buffer.
    folium.Polygon(
        hub['yard_boundary'],
        color='#facc15',
        weight=2,
        fill=False,
        dash_array='6,7',
        tooltip=f'GPS uncertainty reference: {GPS_BOUNDARY_METERS:.0f} m'
    ).add_to(m)

# Main map
st.subheader(f'Live Yard Map — {selected_hub_name}')
st.caption(f'🟢 Inside yard  |  🟡 Boundary / GPS uncertainty  |  🔴 Confirmed outside  |  🟣 Parking hotspot  |  '
           f'🟦 Grid zones ({GRID_CELL_M:.0f} m × {GRID_CELL_M:.0f} m, darker = more vehicles; toggle labels in the layer menu)')
if hidden_far:
    st.caption(f'{hidden_far:,} vehicles more than {NEAR_YARD_METERS/1000:g} km from the yard are not drawn '
               f'(tick the option in the sidebar to show them). They are still in the table below.')
m=folium.Map(location=list(hub['center']),zoom_start=hub['zoom'],max_zoom=22,tiles=None,control_scale=True)
add_base(m)
add_grid_layer(m, hub_grid, grid_counts)
add_hotspot_markers(m, selected_hub_name, selected_hotspot)
add_vehicle_layer(m, map_vehicles)
if selected_grid!='All grid zones':
    cell=hub_grid['cells'][selected_grid]
    folium.Rectangle(bounds=cell['bounds'],color='#ef4444',weight=3,fill=False,tooltip=f'Grid {selected_grid}').add_to(m)
    m.location=list(cell['center']); m.options['zoom']=20
if selected_row is not None:
    add_marker(m,selected_row,selected=True)
    m.location=[float(selected_row['Current Known Latitude']),float(selected_row['Current Known Longitude'])]; m.options['zoom']=21
    if selected_hotspot:
        folium.PolyLine(
            [
                [float(selected_row['Current Known Latitude']), float(selected_row['Current Known Longitude'])],
                [selected_hotspot['lat'], selected_hotspot['lon']]
            ],
            color='#7c3aed', weight=4, dash_array='8,7',
            tooltip=f"Vehicle → {selected_hotspot['line']} — {selected_hotspot['point']} • {selected_hotspot['distance_m']:.1f} m"
        ).add_to(m)
folium.LayerControl(collapsed=False).add_to(m); st_folium(m,width=None,height=720,returned_objects=[],key='main_map')

# Grid occupancy
st.subheader(f'Grid Zone Occupancy — {selected_hub_name}')
if grid_counts:
    occ = (
        df[df['Grid Zone'] != OUTSIDE_GRID]
        .groupby('Grid Zone')['Vehicle Number']
        .agg(Vehicles='count', **{'Vehicle Numbers': lambda v: ', '.join(map(str, v))})
        .reset_index()
    )
    order = {n: i for i, n in enumerate(sorted_grid_cells(hub_grid))}
    occ = occ.sort_values('Grid Zone', key=lambda c: c.map(order))
    st.dataframe(occ, width='stretch', hide_index=True)
else:
    st.caption('No vehicles inside any grid zone right now.')

# Vehicle details
st.subheader('Vehicle Details')
if selected_row is not None:
    r=selected_row; detail_cols=st.columns(7)
    for col,(lab,val) in zip(detail_cols,[('Vehicle',r['Vehicle Number']),('Grid Zone',r['Grid Zone']),('Area',r['Detected Zone']),('Status',r.get('Current Status','-')),('Avg Speed',r.get('Average speed','-')),('GPS',r['Geofence Status']),('Fence Distance',f"{r.get('Fence Distance (m)','-')} m")]):
        col.metric(lab,str(val))
    st.info(
        f"📍 {float(r['Current Known Latitude']):.6f}, "
        f"{float(r['Current Known Longitude']):.6f} | "
        f"{r.get('Current Known Address','-')}"
    )
    if selected_hotspot:
        st.caption(
            f"📍 Nearest parking hotspot: {selected_hotspot['line']} — {selected_hotspot['point']}"
            f" • {selected_hotspot['distance_m']:.1f} m away"
        )
    if gps_source == 'LIVE API':
        st.caption(
            f"Device: {r.get('Device ID','-')} • "
            f"GPS timestamp: {r.get('Timestamp','-')} • "
            f"Battery: {r.get('Battery Level','-')}"
        )
else: st.info('Search a vehicle number in the sidebar to locate it precisely on the map.')

# Table
st.subheader('Fleet Snapshot')
table_cols=['Vehicle Number','Grid Zone','Detected Zone','Current Status','Average speed','Top speed','Current Known Address','Current Known Latitude','Current Known Longitude','Geofence Status','Fence Distance (m)']
st.dataframe(map_df[[c for c in table_cols if c in map_df.columns]],width='stretch',hide_index=True)
st.caption(f'GPS source: {gps_source} • {gps_source_detail} • 🟣 Hotspots are physical reference points; nearest-hotspot distance is approximate and does not represent an exact parking slot assignment.')


st.divider()
with st.expander("⚙️ How to add another hub"):
    st.markdown("""
**You only need to edit the `HUBS` section at the top of this file.**

For each new hub provide:
1. `center` — map center latitude/longitude
2. `yard_boundary` — GPS coordinates around the physical fence
3. `gate` — gate coordinates
4. `zones` — polygons and capacities for Yard, Repair, RTA, Driver Waiting, etc.

The same GPS Excel loader, clustering, vehicle search, exact marker view, Inside / Boundary / Outside logic, and parking hotspot logic will then work automatically for that hub.

**Grid zones:** every hub is covered automatically by a 15 m × 15 m grid over its boundary and zones. Rows are letters north → south, columns numbers west → east (A1, C4, D5 …). Change `GRID_CELL_M` to resize.

**Parking hotspots:** add physical parking reference points under `PARKING_HOTSPOTS` using `line`, `point`, `lat`, and `lon`. When a vehicle is searched, the nearest hotspot is highlighted and the distance is shown.

**Important:** use the actual physical fence/yard boundary, not a large visual
rectangle around the property. The 15 m uncertainty band is applied around that
boundary to avoid treating normal GPS drift as a confirmed yard exit.
""")
