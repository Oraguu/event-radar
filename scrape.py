#!/usr/bin/env python3
"""Event Radar Scraper — Boston Area"""
import json, re, traceback
from datetime import datetime
from pathlib import Path
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "EventRadar/1.0 (github.com/Oraguu/event-radar)"}

TAG_RULES = [
    (["robot", "humanoid", "massrobotics", "manipulation", "locomotion"], "robotics"),
    (["drone", "uav", "uas", "unmanned", "fpv", "aerial"], "drones"),
    (["manufactur", "3d print", "additive", "cnc", "hardware meetup", "fabricat", "device"], "manufacturing"),
    (["ai ", "artificial intelligence", "machine learning", "deep learning", "llm", "neural", "computer vision", "generative"], "ai"),
    (["startup", "entrepreneur", "venture", "pitch", "accelerat", "incubator", "demo day", "founder"], "startup"),
    (["networking", "mixer", "career fair", "cross university"], "networking"),
]
EXCLUDE = ["basketball","hockey","football","baseball","softball","lacrosse","yoga","meditation","worship","prayer","intramural","parking","dining","meal plan","commencement ceremony"]

def tag_for(t, d=""):
    x = (t + " " + d).lower()
    for kws, tag in TAG_RULES:
        if any(k in x for k in kws): return tag
    return "talk"

def bad(t, d=""):
    x = (t + " " + d).lower()
    return any(k in x for k in EXCLUDE)

def clean(s):
    if not s: return ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()[:400]

def scrape_localist(name, url):
    out = []
    try:
        r = requests.get(url, params={"days": 90, "pp": 100}, headers=HEADERS, timeout=30)
        r.raise_for_status()
        for item in r.json().get("events", []):
            ev = item.get("event", item)
            title = ev.get("title", "")
            desc = clean(ev.get("description_text", ev.get("description", "")))
            if bad(title, desc) or not title or len(title) < 3: continue
            ds = ev.get("first_date", ev.get("date", ""))
            if not ds: continue
            try:
                dt = datetime.fromisoformat(ds.replace("Z", "+00:00"))
                date, time = dt.strftime("%Y-%m-%d"), dt.strftime("%-I:%M %p") if dt.hour else "TBD"
            except: date, time = ds[:10], "TBD"
            out.append(dict(date=date, title=title, source=name, tag=tag_for(title, desc),
                            desc=desc[:300], link=ev.get("localist_url", ev.get("url", "")), time=time,
                            location=ev.get("location_name", "")))
        print(f"  OK  {name}: {len(out)} events")
    except Exception as e:
        print(f"  ERR {name}: {e}"); traceback.print_exc()
    return out

def scrape_html(url, source, dtag="talk"):
    out = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.select("article, .event, [class*='event-card'], .views-row, [class*='tribe']"):
            ti = card.select_one("h2, h3, h4, [class*='title']")
            if not ti: continue
            title = clean(ti.get_text())
            if not title or len(title) < 5 or bad(title): continue
            de = card.select_one("p, .description, [class*='desc'], .summary")
            desc = clean(de.get_text()) if de else ""
            li = card.select_one("a[href]")
            link = li["href"] if li else url
            if link.startswith("/"): link = "/".join(url.split("/")[:3]) + link
            te = card.select_one("time, [datetime], [class*='date']")
            date = ""
            if te:
                raw = te.get("datetime", te.get_text())
                for fmt in ["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%B %d, %Y", "%b %d, %Y"]:
                    try: date = datetime.strptime(raw.strip()[:25], fmt).strftime("%Y-%m-%d"); break
                    except: pass
            tg = tag_for(title, desc)
            out.append(dict(date=date or "TBD", title=title, source=source, tag=tg if tg != "talk" else dtag,
                            desc=desc[:300], link=link, time="TBD"))
        print(f"  OK  {source}: {len(out)} events")
    except Exception as e:
        print(f"  ERR {source}: {e}"); traceback.print_exc()
    return out

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
            out.append(dict(date=date or "TBD", title=title, source="Meetup", tag=tag_for(title, name), desc="", link=link, time="TBD"))
        print(f"  OK  {name}: {len(out)} events")
    except Exception as e:
        print(f"  ERR {name}: {e}")
    return out

STATIC = [
    dict(date="2026-02-25", title="Venturing@Harvard Cross University Mixer", source="Harvard i-lab", tag="networking", desc="Monthly meetup for student innovators from NEU, MIT, BU, Babson, Tufts. Harvard i-lab Lobby, Batten Hall.", link="https://innovationlabs.harvard.edu/events/cross-university-mixer", time="4:30 PM", pick=True, pickNote="#1 EASIEST WIN. Designed for cross-university networking"),
    dict(date="2026-02-25", title="Boston Generative AI Meetup", source="Meetup", tag="ai", desc="Video, Image, and Vision AI in Business and Life. World's largest AI meetup.", link="https://www.meetup.com/boston-generative-ai-meetup/", time="Evening"),
    dict(date="2026-02-28", title="Tough Tech Venturing Workshop", source="Harvard SEAS", tag="startup", desc="Full-day bootcamp: team building, market selection, fundraising, IP. HBS faculty.", link="https://events.seas.harvard.edu/event/tough-tech-venturing-workshop", time="8:30 AM", pick=True, pickNote="Tailor-made for robotics entrepreneurship"),
    dict(date="2026-03-05", title="Greentown Labs Climatetech Intern Fair", source="Greentown Labs", tag="networking", desc="Connect with climatetech startups hiring. 444 Somerville Ave.", link="https://greentownlabs.com/events/", time="4:00 PM", pick=True, pickNote="Hardware startups hiring — you have the Mowze experience"),
    dict(date="2026-03-19", title="MTLC Tech Hot Topics", source="Community", tag="networking", desc="Massachusetts Technology Leadership Council networking.", link="https://www.mtlc.co/all-events/", time="5:00 PM"),
    dict(date="2026-03-26", title="A Fresh Start for Our Cities — Bill McKibben", source="Harvard GSD", tag="talk", desc="Renewable energy transforming the built environment.", link="https://www.gsd.harvard.edu/", time="Evening"),
    dict(date="2026-03-28", title="Harvard VC Group Entrepreneurship Summit", source="Harvard", tag="startup", desc="VC and entrepreneurship summit. The Newbury Boston.", link="https://allevents.in/boston/entrepreneurship", time="9:00 AM", pick=True, pickNote="VC networking — how hardware gets funded"),
    dict(date="2026-03-31", title="Mastering Intelligent Failures — Amy Edmondson", source="Harvard HBS", tag="talk", desc="Prof. Edmondson + CEO of Kraft Analytics. Batten Hall, Hive 301.", link="https://events.hbs.edu/", time="3:00 PM"),
    dict(date="2026-04-08", title="Beyond the Cradle: Envisioning a New Space Age", source="MIT Media Lab", tag="talk", desc="10th annual space event. MIT Media Lab, E14, 6th Floor.", link="https://www.media.mit.edu/events/", time="TBD"),
    dict(date="2026-04-09", title="Imagination in Action AI Summit", source="MIT Media Lab", tag="ai", desc="AI leaders + researchers at MIT Media Lab.", link="https://www.imaginationinaction.co/", time="All Day", pick=True, pickNote="AI leaders at MIT Media Lab — high-caliber networking"),
    dict(date="2026-04-13", title="RAPID + TCT 2026", source="Conference", tag="manufacturing", desc="North America's largest additive manufacturing event. Boston Convention Center.", link="https://www.rapid3devent.com/", time="9:00 AM", pick=True, pickNote="Additive manufacturing + aerospace defense. Ask about academic discount"),
    dict(date="2026-04-14", title="AeroDef Manufacturing (co-located w/ RAPID)", source="Conference", tag="manufacturing", desc="Aerospace & defense manufacturing. AI, digital twins, autonomy. Boston.", link="https://www.aerodefevent.com/", time="9:00 AM", pick=True, pickNote="Autonomy, AI, digital twins — directly relevant to your career path"),
    dict(date="2026-04-22", title="MIT KSC: Innovation in Global Growth Markets", source="MIT Sloan", tag="startup", desc="Entrepreneurship, innovation ecosystems, ethical tech.", link="https://mitsloan.mit.edu/ksc/annual-conference", time="All Day"),
    dict(date="2026-04-25", title="National Drone Safety Day", source="FAA", tag="drones", desc="FAA-sponsored: fly-ins, STEM demos, pilot training nationwide.", link="https://www.thedronegirl.com/2026/02/06/2026-drone-events/", time="All Day", pick=True, pickNote="You have your Part 107. Show up, fly, network"),
    dict(date="2026-05-11", title="AUVSI XPONENTIAL 2026", source="AUVSI", tag="drones", desc="World's largest unmanned systems conf. 8,500+ experts. Detroit, MI.", link="https://xponential.org/", time="All Day", pick=True, pickNote="World's largest unmanned systems conf. Worth the trip"),
    dict(date="2026-05-22", title="DroneArt Show Boston", source="Event", tag="drones", desc="Candlelit concert + drone show. Ohiri Field, 95 N Harvard St.", link="https://thedroneartshow.com/boston/", time="Evening"),
    dict(date="2026-05-27", title="Robotics Summit & Expo — Day 1", source="MassRobotics", tag="robotics", desc="6,000+ devs, 50+ sessions, 250+ exhibitors. Boston Convention Center.", link="https://www.roboticssummit.com/", time="9:00 AM", pick=True, pickNote="THE MUST-ATTEND. Block these dates NOW"),
    dict(date="2026-05-28", title="Robotics Summit & Expo — Day 2", source="MassRobotics", tag="robotics", desc="Women in Robotics Breakfast 8am. Career fair, networking.", link="https://www.roboticssummit.com/", time="8:00 AM", pick=True, pickNote="Career fair + continued expo. Don't skip day 2"),
    dict(date="2026-06-22", title="Automate 2026", source="Conference", tag="manufacturing", desc="Premier robotics + automation show. Chicago, IL.", link="https://www.automateshow.com/", time="All Day", pick=True, pickNote="Premier robotics + automation manufacturing show"),
    dict(date="2026-09-01", title="Commercial UAV Expo", source="Conference", tag="drones", desc="Leading commercial UAS trade show. Las Vegas.", link="https://www.expouav.com/", time="All Day"),
    dict(date="2026-09-22", title="BioProcess International", source="Conference", tag="manufacturing", desc="3,200+ scientists. Biopharmaceutical manufacturing. Hynes, Boston.", link="https://informaconnect.com/bioprocessinternational/", time="All Day"),
    dict(date="2026-10-27", title="Tough Tech Summit 2026", source="The Engine", tag="startup", desc="Deep tech founders, investors. Hotel Commonwealth, Boston.", link="https://engine.xyz/toughtechsummit", time="All Day", pick=True, pickNote="Deep tech founders and investors. Spun out of MIT"),
]

RECURRING = [
    dict(title="MIT Robotics Seminar", freq="Check schedule", source="MIT", tag="robotics", desc="Flagship robotics talk series.", link="https://robotics.mit.edu/robotics-seminar/", pick=True, pickNote="Attend regularly — meet your future colleagues"),
    dict(title="MIT CSAIL Seminars", freq="Multiple/week", source="MIT CSAIL", tag="ai", desc="AI, robotics, HCI, computer vision.", link="https://www.csail.mit.edu/events"),
    dict(title="MIT Schwarzman College", freq="Multiple/week", source="MIT", tag="ai", desc="AI4Society seminars. Building 45.", link="https://calendar.mit.edu/department/mit_schwarzman_college_of_computing"),
    dict(title="MIT E-Club", freq="Tuesdays 6pm", source="MIT", tag="startup", desc="Pitch practice, startup seminars.", link="https://web.mit.edu/e-club/"),
    dict(title="MIT $100K Competition", freq="Sep-May", source="MIT", tag="startup", desc="$300K+ in prizes.", link="https://www.mit100k.org/", pick=True, pickNote="Watch the finals live at MIT Media Lab"),
    dict(title="MIT Media Lab Perspectives", freq="Periodic", source="MIT Media Lab", tag="talk", desc="Distinguished speaker series. Free.", link="https://www.media.mit.edu/events/ml-perspectives/"),
    dict(title="Venturing@Harvard Mixer", freq="Monthly", source="Harvard i-lab", tag="networking", desc="Cross-university. NEU welcome. Batten Hall.", link="https://innovationlabs.harvard.edu/events/cross-university-mixer", pick=True, pickNote="#1 EASIEST WIN. Go every month"),
    dict(title="Harvard Grid Events", freq="Periodic", source="Harvard", tag="startup", desc="Engineering startup events.", link="https://www.grid.harvard.edu/"),
    dict(title="Harvard OTD Events", freq="Periodic", source="Harvard", tag="startup", desc="Bio salons, bootcamps, pitch days.", link="https://otd.harvard.edu/events/"),
    dict(title="NEU Sherman Center", freq="Periodic", source="Northeastern", tag="startup", desc="Tech Rebels speakers, Generate Showcase.", link="https://sherman.center.northeastern.edu/", pick=True, pickNote="YOUR school's engineering entrepreneurship hub"),
    dict(title="NEU Generate Showcase", freq="End-of-semester", source="Northeastern", tag="manufacturing", desc="Student product dev demo day.", link="https://sherman.center.northeastern.edu/", pick=True, pickNote="YOUR school's hardware demo day"),
    dict(title="NEU Experiential Robotics", freq="Periodic", source="Northeastern", tag="robotics", desc="Autonomous systems, soft robotics.", link="https://robotics.northeastern.edu/", pick=True, pickNote="Your university's robotics hub"),
    dict(title="Startup Grind Boston", freq="Monthly", source="Community", tag="startup", desc="Fireside chats, pitch nights. 11K members.", link="https://www.startupgrind.com/boston/", pick=True, pickNote="Monthly founder fireside chats"),
    dict(title="Boston Hardware Meetup", freq="~Monthly", source="Community", tag="manufacturing", desc="Formlabs, Greentown, The Engine.", link="https://luma.com/bos-hardware-meetup", pick=True, pickNote="Your tribe — hardware builders"),
    dict(title="Boston ENET", freq="Monthly (Sep-Jun)", source="Community", tag="startup", desc="IEEE-affiliated. Expert panels + networking.", link="https://bostonenet.org/", pick=True, pickNote="IEEE, early-stage hardware startups"),
    dict(title="Venture Cafe Cambridge", freq="Weekly (Thu)", source="Venture Cafe", tag="networking", desc="Free weekly. Kendall Sq.", link="https://venturecafecambridge.org/", pick=True, pickNote="Free every Thursday. Just drop in"),
    dict(title="AI Tinkerers Boston", freq="Monthly", source="Meetup", tag="ai", desc="Code-first demos, hackathons.", link="https://boston.aitinkerers.org/", pick=True, pickNote="Code-first builders"),
    dict(title="Boston Gen AI Meetup", freq="Monthly", source="Meetup", tag="ai", desc="World's largest AI meetup.", link="https://www.meetup.com/boston-generative-ai-meetup/"),
    dict(title="Boston CV AIR", freq="Regular", source="Meetup", tag="robotics", desc="Autonomous robotics, CV.", link="https://www.meetup.com/boston-air/", pick=True, pickNote="Autonomous robotics — your wheelhouse"),
    dict(title="Boston Drone Racing", freq="Weekly", source="BU-based", tag="drones", desc="FPV racing & hack nights. $3/session.", link="http://bostondrone.racing/", pick=True, pickNote="Part 107 holder. Build drones here"),
    dict(title="MassRobotics Events", freq="Periodic", source="MassRobotics", tag="robotics", desc="Boston's robotics hub. 12 Channel St.", link="https://www.massrobotics.org/events/", pick=True, pickNote="Your industry's home base"),
    dict(title="Greentown Labs", freq="Periodic", source="Greentown Labs", tag="manufacturing", desc="Climatetech incubator. Somerville.", link="https://greentownlabs.com/events/"),
    dict(title="The Engine Events", freq="Periodic", source="The Engine", tag="startup", desc="MIT deep tech VC.", link="https://engine.xyz/", pick=True, pickNote="Deep tech VC — serious founders"),
    dict(title="FORGE", freq="Periodic", source="Community", tag="manufacturing", desc="Prototype to production.", link="https://www.forgehq.com/", pick=True, pickNote="Your Mowze path"),
    dict(title="BU Spark!", freq="Weekly (Wed)", source="BU", tag="ai", desc="Tech incubator. Hackathons, Demo Days.", link="https://www.bu.edu/spark/events/"),
    dict(title="TiE Boston", freq="Monthly", source="Community", tag="networking", desc="Angel investor network.", link="https://boston.tie.org/"),
    dict(title="Mass Innovation Nights", freq="Monthly", source="Community", tag="startup", desc="Monthly product showcases.", link="https://mass.innovationnights.com/"),
    dict(title="AUVSI New England", freq="Periodic", source="Community", tag="drones", desc="Drone/UAS workshops.", link="https://www.auvsi.org/"),
    dict(title="MIT Sloan Conferences", freq="Multiple/semester", source="MIT Sloan", tag="startup", desc="Student-led: tech, healthcare, fintech.", link="https://mitsloan.mit.edu/events"),
]

SOURCE_LINKS = [
    dict(label="MIT Events", url="https://calendar.mit.edu/"),
    dict(label="MIT CSAIL", url="https://www.csail.mit.edu/events"),
    dict(label="MIT Robotics", url="https://robotics.mit.edu/robotics-seminar/"),
    dict(label="MIT Schwarzman", url="https://calendar.mit.edu/department/mit_schwarzman_college_of_computing"),
    dict(label="MIT Media Lab", url="https://www.media.mit.edu/events/"),
    dict(label="Harvard SEAS", url="https://events.seas.harvard.edu/"),
    dict(label="Harvard i-lab", url="https://innovationlabs.harvard.edu/"),
    dict(label="Northeastern", url="https://calendar.northeastern.edu/"),
    dict(label="NEU Sherman", url="https://sherman.center.northeastern.edu/"),
    dict(label="BU Spark!", url="https://www.bu.edu/spark/events/"),
    dict(label="MassRobotics", url="https://www.massrobotics.org/events/"),
    dict(label="Greentown Labs", url="https://greentownlabs.com/events/"),
    dict(label="The Engine", url="https://engine.xyz/"),
    dict(label="Startup Boston", url="https://www.startupbos.org/directory/events"),
    dict(label="Venture Cafe", url="https://venturecafecambridge.org/"),
    dict(label="Eventbrite", url="https://www.eventbrite.com/d/ma--boston/"),
]

def main():
    print("=" * 60)
    print(f"Event Radar Scraper — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    all_ev = []
    print("\n[1/4] University calendars (Localist API — keeping ALL events)...")
    for name, url in [
        ("MIT", "https://calendar.mit.edu/api/2/events"),
        ("Northeastern", "https://calendar.northeastern.edu/api/2/events"),
        ("Harvard SEAS", "https://events.seas.harvard.edu/api/2/events"),
    ]:
        all_ev.extend(scrape_localist(name, url))
    print("\n[2/4] HTML sources...")
    all_ev.extend(scrape_html("https://www.csail.mit.edu/events", "MIT CSAIL", "ai"))
    all_ev.extend(scrape_html("https://www.massrobotics.org/events/", "MassRobotics", "robotics"))
    all_ev.extend(scrape_html("https://greentownlabs.com/events/", "Greentown Labs", "manufacturing"))
    print("\n[3/4] Meetup groups...")
    for url, name in [
        ("https://www.meetup.com/boston-generative-ai-meetup/", "Boston Gen AI"),
        ("https://www.meetup.com/boston-air/", "Boston CV AIR"),
        ("https://www.meetup.com/the-boston-robotics-meetup-group/", "Boston Robotics"),
        ("https://www.meetup.com/startups-and-tech-events-in-boston/", "Startup Valley"),
    ]:
        all_ev.extend(scrape_meetup(url, name))
    print(f"\n[4/4] Static events: +{len(STATIC)}")
    all_ev.extend(STATIC)
    seen, deduped = set(), []
    for e in all_ev:
        k = (e.get("title", "").lower()[:50], e.get("date", ""))
        if k not in seen: seen.add(k); deduped.append(e)
    today = datetime.now().strftime("%Y-%m-%d")
    future = sorted([e for e in deduped if e.get("date", "TBD") >= today or e.get("date") == "TBD"], key=lambda e: e.get("date", "9999"))
    print(f"\n{'='*60}\nResult: {len(future)} upcoming events\n{'='*60}")
    output = dict(scraped_at=datetime.now().isoformat(), event_count=len(future), events=future, recurring=RECURRING, source_links=SOURCE_LINKS)
    out = Path(__file__).parent / "events.json"
    out.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"Wrote {out}")

if __name__ == "__main__":
    main()
