#!/usr/bin/env python3
"""
Event Radar Scraper
Scrapes Boston-area university calendars, meetup groups, and industry sources.
Outputs events.json for the frontend to read.
"""

import json
import re
import traceback
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "EventRadar/1.0 (Boston area event aggregator)"
}

# ── Relevance Filtering ────────────────────────────────────────────────

INCLUDE_KW = [
    "robot", "drone", "uav", "uas", "autonomous", "automation",
    "manufactur", "hardware", "3d print", "additive", "cnc", "fabricat",
    "startup", "entrepreneur", "venture", "pitch", "demo day", "accelerat",
    "ai ", "artificial intelligence", "machine learning", "deep learning",
    "computer vision", "neural", "llm", "generative ai",
    "engineer", "mechan", "sensor", "embedd",
    "networking", "mixer", "career fair", "hackathon",
    "innovation", "incubator", "maker", "prototype",
    "aerospace", "defense", "space", "seminar", "colloqui",
]
EXCLUDE_KW = [
    "basketball", "hockey", "football", "baseball", "softball", "lacrosse",
    "yoga", "meditation", "worship", "prayer", " mass ",
    "alumni reunion", "commencement", "graduation ceremony",
    "parking", "dining", "meal plan", "intramural",
]
TAG_RULES = [
    (["robot", "robotics summit", "massrobotics", "humanoid"], "robotics"),
    (["drone", "uav", "uas", "unmanned", "part 107", "fpv"], "drones"),
    (["manufactur", "3d print", "additive", "cnc", "hardware meetup", "fabricat", "rapid +", "aerodef", "device"], "manufacturing"),
    (["ai ", "artificial intelligence", "machine learning", "deep learning", "llm", "neural", "computer vision", "generative"], "ai"),
    (["startup", "entrepreneur", "venture", "pitch", "accelerat", "incubator", "demo day", "$100k", "founder"], "startup"),
    (["networking", "mixer", "career fair", "cross university", "connect", "social"], "networking"),
]

def tag_for(title, desc=""):
    t = (title + " " + desc).lower()
    for kws, tag in TAG_RULES:
        if any(k in t for k in kws):
            return tag
    return "talk"

def relevant(title, desc=""):
    t = (title + " " + desc).lower()
    if any(k in t for k in EXCLUDE_KW):
        return False
    return any(k in t for k in INCLUDE_KW)

def clean(s):
    if not s: return ""
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()[:400]

# ── Localist API (MIT, Northeastern, Harvard SEAS) ─────────────────────

LOCALIST = [
    ("MIT",            "https://calendar.mit.edu/api/2/events"),
    ("Northeastern",   "https://calendar.northeastern.edu/api/2/events"),
    ("Harvard SEAS",   "https://events.seas.harvard.edu/api/2/events"),
]

def scrape_localist(name, url):
    out = []
    try:
        r = requests.get(url, params={"days": 90, "pp": 100}, headers=HEADERS, timeout=30)
        r.raise_for_status()
        for item in r.json().get("events", []):
            ev = item.get("event", item)
            title = ev.get("title", "")
            desc = clean(ev.get("description_text", ev.get("description", "")))
            if not relevant(title, desc): continue
            ds = ev.get("first_date", ev.get("date", ""))
            if not ds: continue
            try:
                dt = datetime.fromisoformat(ds.replace("Z", "+00:00"))
                date, time = dt.strftime("%Y-%m-%d"), dt.strftime("%-I:%M %p") if dt.hour else "TBD"
            except Exception:
                date, time = ds[:10], "TBD"
            out.append(dict(date=date, title=title, source=name, tag=tag_for(title, desc),
                            desc=desc[:300], link=ev.get("localist_url", ev.get("url", "")),
                            time=time, location=ev.get("location_name", "")))
        print(f"  OK  {name}: {len(out)} events")
    except Exception as e:
        print(f"  ERR {name}: {e}")
    return out

# ── Generic HTML scraper helper ────────────────────────────────────────

def scrape_html(url, source, default_tag="talk", selectors=None):
    """Generic scraper that tries common event-page patterns."""
    sel = selectors or {}
    out = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select(sel.get("card", "article, .event, [class*='event-card'], .views-row"))
        for card in cards:
            ti = card.select_one(sel.get("title", "h2, h3, h4, [class*='title']"))
            if not ti: continue
            title = clean(ti.get_text())
            if not title or len(title) < 5: continue
            de = card.select_one(sel.get("desc", "p, .description, [class*='desc'], .summary"))
            desc = clean(de.get_text()) if de else ""
            li = card.select_one("a[href]")
            link = li["href"] if li else url
            if link.startswith("/"): link = "/".join(url.split("/")[:3]) + link
            te = card.select_one("time, [datetime], [class*='date']")
            date = ""
            if te:
                raw = te.get("datetime", te.get_text())
                for fmt in ["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d", "%B %d, %Y", "%b %d, %Y"]:
                    try:
                        date = datetime.strptime(raw.strip()[:25], fmt).strftime("%Y-%m-%d"); break
                    except Exception: pass
            if relevant(title, desc) or default_tag in ("robotics", "manufacturing"):
                out.append(dict(date=date or "TBD", title=title, source=source,
                                tag=tag_for(title, desc) if relevant(title, desc) else default_tag,
                                desc=desc[:300], link=link, time="TBD"))
        print(f"  OK  {source}: {len(out)} events")
    except Exception as e:
        print(f"  ERR {source}: {e}")
    return out

# ── Meetup group scraper ───────────────────────────────────────────────

def scrape_meetup(url, name):
    out = []
    try:
        r = requests.get(url.rstrip("/") + "/events/", headers=HEADERS, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.select("[id*='event'], [class*='eventCard'], [data-testid*='event']"):
            ti = card.select_one("h2, h3, span[class*='name'], [class*='title']")
            if not ti: continue
            title = clean(ti.get_text())
            if not title: continue
            li = card.select_one("a[href*='/events/']")
            link = li["href"] if li else url
            if link.startswith("/"): link = "https://www.meetup.com" + link
            te = card.select_one("time")
            date = te.get("datetime", "")[:10] if te else ""
            out.append(dict(date=date or "TBD", title=title, source="Meetup",
                            tag=tag_for(title, name), desc="", link=link, time="TBD"))
        print(f"  OK  {name}: {len(out)} events")
    except Exception as e:
        print(f"  ERR {name}: {e}")
    return out

# ── Static events (conferences with fixed dates) ──────────────────────

STATIC = [
    dict(date="2026-04-13", title="RAPID + TCT 2026", source="Conference", tag="manufacturing",
         desc="North America's largest additive manufacturing event. Boston Convention Center. Academic discounts.", link="https://www.rapid3devent.com/", time="9:00 AM",
         pick=True, pickNote="Additive manufacturing + aerospace defense. Ask about academic discount"),
    dict(date="2026-04-14", title="AeroDef Manufacturing (co-located w/ RAPID)", source="Conference", tag="manufacturing",
         desc="Aerospace & defense manufacturing. AI, digital twins, autonomy, supply chain. Boston Convention Center.", link="https://www.aerodefevent.com/", time="9:00 AM",
         pick=True, pickNote="Autonomy, AI, digital twins — directly relevant to your career path"),
    dict(date="2026-04-25", title="National Drone Safety Day", source="FAA", tag="drones",
         desc="FAA-sponsored: fly-ins, STEM demos, pilot training. Events nationwide.", link="https://www.thedronegirl.com/2026/02/06/2026-drone-events/", time="All Day",
         pick=True, pickNote="You have your Part 107. Show up, fly, network with commercial operators"),
    dict(date="2026-05-11", title="AUVSI XPONENTIAL 2026", source="AUVSI", tag="drones",
         desc="World's largest unmanned systems conference. 8,500+ experts. Startup pavilion. Detroit, MI.", link="https://xponential.org/", time="All Day",
         pick=True, pickNote="World's largest unmanned systems conf. Worth the Detroit trip"),
    dict(date="2026-05-22", title="DroneArt Show Boston", source="Event", tag="drones",
         desc="Candlelit concert + synchronized drone show. Ohiri Field, 95 N Harvard St.", link="https://thedroneartshow.com/boston/", time="Evening"),
    dict(date="2026-05-27", title="Robotics Summit & Expo — Day 1", source="MassRobotics", tag="robotics",
         desc="6,000+ devs. 50+ sessions, 250+ exhibitors, live demos, RBR50 Awards. Boston Convention Center.", link="https://www.roboticssummit.com/", time="9:00 AM",
         pick=True, pickNote="THE MUST-ATTEND. Block these dates NOW. Email for academic discount"),
    dict(date="2026-05-28", title="Robotics Summit & Expo — Day 2", source="MassRobotics", tag="robotics",
         desc="Women in Robotics Breakfast 8am. Keynotes, career fair, networking. Boston Convention Center.", link="https://www.roboticssummit.com/", time="8:00 AM",
         pick=True, pickNote="Career fair + continued expo. Don't skip day 2"),
    dict(date="2026-06-22", title="Automate 2026", source="Conference", tag="manufacturing",
         desc="Premier robotics + automation + smart manufacturing show. Chicago, IL.", link="https://www.automateshow.com/", time="All Day",
         pick=True, pickNote="Premier robotics + automation manufacturing show"),
    dict(date="2026-09-01", title="Commercial UAV Expo", source="Conference", tag="drones",
         desc="Leading international commercial UAS trade show. Las Vegas.", link="https://www.expouav.com/", time="All Day"),
    dict(date="2026-09-22", title="BioProcess International", source="Conference", tag="manufacturing",
         desc="3,200+ scientists. Biopharmaceutical manufacturing. Hynes Convention Center, Boston.", link="https://informaconnect.com/bioprocessinternational/", time="All Day"),
    dict(date="2026-10-27", title="Tough Tech Summit 2026", source="The Engine", tag="startup",
         desc="Deep tech founders, investors. Robotics, energy, hard science. Hotel Commonwealth, Boston.", link="https://engine.xyz/toughtechsummit", time="All Day",
         pick=True, pickNote="Deep tech founders and investors. The Engine was spun out of MIT"),
]

# ── Recurring series (manually maintained) ─────────────────────────────

RECURRING = [
    dict(title="MIT Robotics Seminar", freq="Check schedule", source="MIT", tag="robotics",
         desc="Flagship robotics talk series — top researchers from industry and academia.", link="https://robotics.mit.edu/robotics-seminar/",
         pick=True, pickNote="Attend regularly — meet the people building what you want to build"),
    dict(title="MIT CSAIL Seminars", freq="Multiple/week", source="MIT CSAIL", tag="ai",
         desc="Regular seminars on AI, robotics, HCI, computer vision.", link="https://www.csail.mit.edu/events"),
    dict(title="MIT Schwarzman College of Computing", freq="Multiple/week", source="MIT", tag="ai",
         desc="AI4Society seminars, distinguished lectures. Building 45, 51 Vassar St.", link="https://calendar.mit.edu/department/mit_schwarzman_college_of_computing"),
    dict(title="MIT E-Club", freq="Tuesdays 6pm", source="MIT", tag="startup",
         desc="Open to MIT, Harvard & Wellesley. Pitch practice, startup seminars. Room 56-114.", link="https://web.mit.edu/e-club/"),
    dict(title="MIT $100K Competition", freq="Sep-May", source="MIT", tag="startup",
         desc="Pitch → Accelerate → Launch. $300K+ in prizes. Open to Greater Boston.", link="https://www.mit100k.org/",
         pick=True, pickNote="Watch the finals live at MIT Media Lab"),
    dict(title="MIT Media Lab Perspectives", freq="Periodic", source="MIT Media Lab", tag="talk",
         desc="Distinguished speaker series. Free, livestream open to public.", link="https://www.media.mit.edu/events/ml-perspectives/"),
    dict(title="Venturing@Harvard Cross-University Mixer", freq="Monthly", source="Harvard i-lab", tag="networking",
         desc="Open to NEU, MIT, BU, Tufts, Babson & more. Harvard i-lab, Batten Hall.", link="https://innovationlabs.harvard.edu/events/cross-university-mixer",
         pick=True, pickNote="#1 EASIEST WIN. Designed for cross-university networking. Just show up every month"),
    dict(title="Harvard Grid Events", freq="Periodic", source="Harvard", tag="startup",
         desc="Applied Sciences & Engineering startup events.", link="https://www.grid.harvard.edu/"),
    dict(title="Harvard OTD Events", freq="Periodic", source="Harvard", tag="startup",
         desc="Office of Technology Development — bio salons, bootcamps, pitch days.", link="https://otd.harvard.edu/events/"),
    dict(title="NEU Sherman Center Events", freq="Periodic", source="Northeastern", tag="startup",
         desc="Engineering entrepreneurship: Tech Rebels speakers, Generate Showcase. Hayden Hall.", link="https://sherman.center.northeastern.edu/",
         pick=True, pickNote="YOUR school's engineering entrepreneurship hub"),
    dict(title="NEU Generate Showcase", freq="End-of-semester", source="Northeastern", tag="manufacturing",
         desc="Student product development demo day. Hardware projects, concept to prototype.", link="https://sherman.center.northeastern.edu/",
         pick=True, pickNote="YOUR school's hardware demo day. Find collaborators here"),
    dict(title="NEU Experiential Robotics", freq="Periodic", source="Northeastern", tag="robotics",
         desc="Seminars on autonomous systems, underwater robots, soft robotics.", link="https://robotics.northeastern.edu/",
         pick=True, pickNote="Your own university's robotics research hub"),
    dict(title="Startup Grind Boston", freq="Monthly", source="Community", tag="startup",
         desc="Fireside chats, panels, pitch nights. 11,000+ members.", link="https://www.startupgrind.com/boston/",
         pick=True, pickNote="Monthly founder fireside chats. Great for expanding your circle"),
    dict(title="Boston Hardware Meetup", freq="~Monthly", source="Community", tag="manufacturing",
         desc="Hardware professionals. Formlabs, Greentown Labs, The Engine.", link="https://luma.com/bos-hardware-meetup",
         pick=True, pickNote="Your tribe — hardware people building physical products"),
    dict(title="Boston ENET", freq="Monthly (Sep-Jun)", source="Community", tag="startup",
         desc="IEEE-affiliated. Expert panels, Q&A, 1.5hrs networking. Since 1991.", link="https://bostonenet.org/",
         pick=True, pickNote="IEEE-affiliated, early-stage hardware startups"),
    dict(title="Venture Cafe Cambridge", freq="Weekly (Thu)", source="Venture Cafe", tag="networking",
         desc="Free weekly gathering. Rotating hardware/robotics/startup sessions. Kendall Square.", link="https://venturecafecambridge.org/",
         pick=True, pickNote="Free every Thursday in Kendall Square. Just drop in"),
    dict(title="AI Tinkerers Boston", freq="Monthly", source="Meetup", tag="ai",
         desc="Code-first demos, hackathons, deep networking for AI builders.", link="https://boston.aitinkerers.org/",
         pick=True, pickNote="Code-first builders — the people you want in your network"),
    dict(title="Boston Generative AI Meetup", freq="Monthly", source="Meetup", tag="ai",
         desc="World's largest AI meetup. Expert panels, demos, networking.", link="https://www.meetup.com/boston-generative-ai-meetup/"),
    dict(title="Boston CV AIR (AI, Autonomy & Robotics)", freq="Regular", source="Meetup", tag="robotics",
         desc="Autonomous robotics, biomedical robotics, computer vision.", link="https://www.meetup.com/boston-air/",
         pick=True, pickNote="Autonomous robotics talks — directly in your wheelhouse"),
    dict(title="Boston Drone Racing Club", freq="Weekly", source="BU-based", tag="drones",
         desc="FPV drone racing & hack nights. Custom builds. $3/session.", link="http://bostondrone.racing/",
         pick=True, pickNote="You have your Part 107. Build drones, meet the FPV community"),
    dict(title="MassRobotics Events", freq="Periodic", source="MassRobotics", tag="robotics",
         desc="World's largest independent robotics hub. 12 Channel St, Boston.", link="https://www.massrobotics.org/events/",
         pick=True, pickNote="Your industry's home base in Boston. Be a regular"),
    dict(title="Greentown Labs Events", freq="Periodic", source="Greentown Labs", tag="manufacturing",
         desc="Climatetech incubator in Somerville. Hardware meetups, demo days.", link="https://greentownlabs.com/events/"),
    dict(title="The Engine Events", freq="Periodic", source="The Engine", tag="startup",
         desc="MIT-spun deep tech VC. Tough Tech Summit, hardware meetups.", link="https://engine.xyz/",
         pick=True, pickNote="Deep tech VC — serious hardware founders and investors"),
    dict(title="FORGE (Prototype to Production)", freq="Periodic", source="Community", tag="manufacturing",
         desc="Nonprofit connecting hardware startups with manufacturers.", link="https://www.forgehq.com/",
         pick=True, pickNote="Prototype to production — the journey you did at Mowze"),
    dict(title="Artisan's Asylum", freq="Ongoing", source="Makerspace", tag="manufacturing",
         desc="Non-profit community makerspace in Somerville.", link="https://www.artisansasylum.com"),
    dict(title="Cambridge Hackspace", freq="Weekly", source="Makerspace", tag="manufacturing",
         desc="Laser cutter, CNC, 3D printers. Somerville.", link="https://www.cambridgehackspace.com/"),
    dict(title="BU Spark!", freq="Weekly (Wed)", source="BU", tag="ai",
         desc="Tech incubator. Hackathons, Demo Days, Ignite clubs.", link="https://www.bu.edu/spark/events/"),
    dict(title="TiE Boston", freq="Monthly", source="Community", tag="networking",
         desc="Entrepreneur and angel investor network.", link="https://boston.tie.org/"),
    dict(title="Mass Innovation Nights", freq="Monthly", source="Community", tag="startup",
         desc="Monthly product showcases for Boston-area startups.", link="https://mass.innovationnights.com/"),
    dict(title="Startup Valley Networking", freq="Biweekly", source="Meetup", tag="startup",
         desc="Pitch & networking at Bar Moxy, Boston.", link="https://www.meetup.com/startups-and-tech-events-in-boston/"),
    dict(title="AUVSI New England", freq="Periodic", source="Community", tag="drones",
         desc="Drone/UAS workshops, networking, policy updates.", link="https://www.auvsi.org/"),
    dict(title="MIT Sloan Conferences", freq="Multiple/semester", source="MIT Sloan", tag="startup",
         desc="Student-led: tech, healthcare, fintech, national security.", link="https://mitsloan.mit.edu/events"),
]

SOURCE_LINKS = [
    dict(label="MIT Events", url="https://calendar.mit.edu/"),
    dict(label="MIT CSAIL", url="https://www.csail.mit.edu/events"),
    dict(label="MIT Robotics", url="https://robotics.mit.edu/robotics-seminar/"),
    dict(label="MIT Schwarzman", url="https://calendar.mit.edu/department/mit_schwarzman_college_of_computing"),
    dict(label="MIT Media Lab", url="https://www.media.mit.edu/events/"),
    dict(label="MIT Sloan", url="https://mitsloan.mit.edu/events"),
    dict(label="Harvard SEAS", url="https://events.seas.harvard.edu/"),
    dict(label="Harvard i-lab", url="https://innovationlabs.harvard.edu/"),
    dict(label="Harvard Grid", url="https://www.grid.harvard.edu/"),
    dict(label="Northeastern", url="https://calendar.northeastern.edu/"),
    dict(label="NEU Sherman Ctr", url="https://sherman.center.northeastern.edu/"),
    dict(label="NEU Robotics", url="https://robotics.northeastern.edu/"),
    dict(label="BU Calendar", url="https://www.bu.edu/calendar/"),
    dict(label="BU Spark!", url="https://www.bu.edu/spark/events/"),
    dict(label="MassRobotics", url="https://www.massrobotics.org/events/"),
    dict(label="Greentown Labs", url="https://greentownlabs.com/events/"),
    dict(label="The Engine", url="https://engine.xyz/"),
    dict(label="HW Meetup", url="https://luma.com/bos-hardware-meetup"),
    dict(label="Drone Racing", url="http://bostondrone.racing/"),
    dict(label="Startup Boston", url="https://www.startupbos.org/directory/events"),
    dict(label="Venture Cafe", url="https://venturecafecambridge.org/"),
    dict(label="Startup Grind", url="https://www.startupgrind.com/boston/"),
    dict(label="Eventbrite", url="https://www.eventbrite.com/d/ma--boston/"),
]

# ── Main ───────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print(f"Event Radar Scraper — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    all_events = []

    print("\n[1/4] University calendars (Localist API)...")
    for name, url in LOCALIST:
        all_events.extend(scrape_localist(name, url))

    print("\n[2/4] HTML sources...")
    all_events.extend(scrape_html("https://www.csail.mit.edu/events", "MIT CSAIL", "ai"))
    all_events.extend(scrape_html("https://www.massrobotics.org/events/", "MassRobotics", "robotics"))
    all_events.extend(scrape_html("https://greentownlabs.com/events/", "Greentown Labs", "manufacturing"))

    print("\n[3/4] Meetup groups...")
    for url, name in [
        ("https://www.meetup.com/boston-generative-ai-meetup/", "Boston Gen AI"),
        ("https://www.meetup.com/boston-air/", "Boston CV AIR"),
        ("https://www.meetup.com/the-boston-robotics-meetup-group/", "Boston Robotics"),
        ("https://www.meetup.com/startups-and-tech-events-in-boston/", "Startup Valley"),
        ("https://www.meetup.com/aittg-boston/", "Boston AI Devs"),
    ]:
        all_events.extend(scrape_meetup(url, name))

    print("\n[4/4] Static events...")
    all_events.extend(STATIC)
    print(f"  +{len(STATIC)} static events")

    # Dedup, filter past, sort
    seen, deduped = set(), []
    for e in all_events:
        k = (e.get("title", "").lower()[:50], e.get("date", ""))
        if k not in seen: seen.add(k); deduped.append(e)
    today = datetime.now().strftime("%Y-%m-%d")
    future = sorted(
        [e for e in deduped if e.get("date", "TBD") >= today or e.get("date") == "TBD"],
        key=lambda e: e.get("date", "9999")
    )

    print(f"\n{'='*60}")
    print(f"Result: {len(future)} upcoming events (from {len(all_events)} raw)")
    print(f"{'='*60}")

    output = dict(
        scraped_at=datetime.now().isoformat(),
        event_count=len(future),
        events=future,
        recurring=RECURRING,
        source_links=SOURCE_LINKS,
    )
    out = Path(__file__).parent / "events.json"
    out.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"\nWrote {out}")

if __name__ == "__main__":
    main()
