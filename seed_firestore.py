"""Seed script for populating Firestore database with LoL matchup data.

HARDCODED PROJECT ID: "qwiklabs-gcp-02-9285eef2192b"
"""

from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-02-9285eef2192b"


def seed_database():
    db = firestore.Client(project=PROJECT_ID)
    matchups_ref = db.collection("matchups")

    seed_data = [
        {
            "id": "yasuo",
            "champion_name": "Yasuo",
            "lane": "Mid",
            "recommended_counters": ["Renekton", "Vex", "Malphite", "Pantheon"],
            "counter_reasons": "CC and burst champions overwhelm Yasuo's mobility. Renekton and Pantheon ignore Wind Wall and stun him instantly.",
            "do_not_pick": ["Lux", "Vel'Koz", "Ahri"],
            "do_not_pick_reasons": "Skillshot-reliant mages get blocked by Wind Wall and dashed on through minion waves.",
            "playstyle_tips": "Bait Wind Wall (26s early CD). Pop his passive shield before all-in. Avoid fighting inside full enemy minion waves.",
        },
        {
            "id": "zed",
            "champion_name": "Zed",
            "lane": "Mid",
            "recommended_counters": ["Lissandra", "Garen", "Malphite"],
            "counter_reasons": "Lissandra R completely negates Death Mark. Point-and-click CC and armor shut down his assassination combos.",
            "do_not_pick": ["Veigar", "Xerath", "Ziggs"],
            "do_not_pick_reasons": "Immobile squishy mages are free targets for Zed's Death Mark at level 6.",
            "playstyle_tips": "Track his Shadow (W) cooldown. Rush Zhonya's Hourglass or Seeker's Armguard. Ping missing immediately.",
        },
        {
            "id": "darius",
            "champion_name": "Darius",
            "lane": "Top",
            "recommended_counters": ["Vayne", "Quinn", "Wukong", "Yorick"],
            "counter_reasons": "Ranged kiting prevents Darius from landing Apprehend (E). Clones and pets block his targeted abilities.",
            "do_not_pick": ["Sion", "Nautilus", "Garen", "Nasus"],
            "do_not_pick_reasons": "Melee tanks give Darius free Hemorrhage 5-stacks and true damage ultimate resets.",
            "playstyle_tips": "Dodge the outer blade of Q to prevent his healing. Never take extended trades past 3 Hemorrhage stacks.",
        },
        {
            "id": "ahri",
            "champion_name": "Ahri",
            "lane": "Mid",
            "recommended_counters": ["Yasuo", "Tristana", "Sylas"],
            "counter_reasons": "Yasuo Wind Wall blocks Charm (E) and Orb (Q). Tristana and Sylas out-trade her all-in damage early.",
            "do_not_pick": ["Lux", "Taliyah"],
            "do_not_pick_reasons": "Ahri's Spirit Rush (R) easily dodges slow skillshots and catches immobile mages.",
            "playstyle_tips": "Stand behind minions to block Charm. Trade when Charm is on cooldown (12s+).",
        },
        {
            "id": "pantheon",
            "champion_name": "Pantheon",
            "lane": "Top / Mid / Support",
            "recommended_counters": ["Ornn", "Malphite", "Gragas", "Morgana"],
            "counter_reasons": "Tanks and displacement CC neutralize Pantheon's point-and-click stun (W) and Aegis Assault (E).",
            "do_not_pick": ["Yasuo", "Kassadin", "Twisted Fate"],
            "do_not_pick_reasons": "Point-and-click stun and Aegis Assault (E) block all frontal damage and interrupt squishy combos.",
            "playstyle_tips": "Respect his empowered W level 1-3 all-in. Wait out Aegis Assault (E) shield before throwing major damage skills.",
        },
    ]

    for item in seed_data:
        doc_id = item["id"]
        data = {k: v for k, v in item.items() if k != "id"}
        matchups_ref.document(doc_id).set(data)
        print(f"Seeded matchup for {item['champion_name']} ({doc_id})")

    print(f"Successfully seeded {len(seed_data)} matchup records into Firestore database (Project: {PROJECT_ID}).")


if __name__ == "__main__":
    seed_database()
