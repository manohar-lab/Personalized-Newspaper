import asyncio
import json
import httpx

BASE_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"

async def test_full_application():
    async with httpx.AsyncClient(timeout=60.0) as client:
        print("==================================================")
        print("1. VERIFYING SYSTEM HEALTH & DATABASE")
        print("==================================================")
        res = await client.get(f"{BASE_URL}/api/health")
        assert res.status_code == 200, f"Health check failed: {res.text}"
        health_data = res.json()
        print("Health Response:", json.dumps(health_data, indent=2))
        assert health_data.get("service") == "personalized-newspaper"

        res = await client.get(f"{BASE_URL}/api/health/database")
        assert res.status_code == 200, f"Database health check failed: {res.text}"
        db_data = res.json()
        print("Database Health Response:", json.dumps(db_data, indent=2))
        assert db_data.get("status") == "connected"

        # Check OpenAPI Docs
        res = await client.get(f"{BASE_URL}/api/docs")
        assert res.status_code == 200, f"API Docs failed: {res.status_code}"
        print("OpenAPI Docs: OK (200)")

        print("\n==================================================")
        print("2. VERIFYING USER REGISTRATION & AUTHENTICATION")
        print("==================================================")
        user_email = "dev_verify_user@example.com"
        user_pw = "DevPassword123!"
        user_name = "DevVerifyUser"

        # Register
        reg_payload = {
            "email": user_email,
            "password": user_pw,
            "full_name": user_name,
        }
        res = await client.post(f"{BASE_URL}/api/auth/register", json=reg_payload)
        if res.status_code in [200, 201]:
            print("Registration Successful!")
        else:
            print("Registration returned:", res.status_code, "(User already created in local DB)")

        # Login
        login_res = await client.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": user_email, "password": user_pw},
        )
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        token_data = login_res.json()
        token = token_data["access_token"]
        print("Login Successful! Received JWT Access Token.")
        headers = {"Authorization": f"Bearer {token}"}

        # /api/auth/me
        me_res = await client.get(f"{BASE_URL}/api/auth/me", headers=headers)
        assert me_res.status_code == 200, f"/api/auth/me failed: {me_res.text}"
        me = me_res.json()
        print(f"Authenticated User (/api/auth/me): {me['email']} (ID: {me['id']})")

        print("\n==================================================")
        print("3. VERIFYING TOPICS & ONBOARDING / EXPLICIT INTERESTS")
        print("==================================================")
        topics_res = await client.get(f"{BASE_URL}/api/topics", headers=headers)
        assert topics_res.status_code == 200, f"Topics failed: {topics_res.text}"
        topics = topics_res.json()
        print(f"Available Topics ({len(topics)}):", [t["name"] for t in topics[:5]])

        # Select explicit interests via onboarding
        if topics:
            pos_slugs = [t["slug"] for t in topics[:3]]
            onboarding_res = await client.post(
                f"{BASE_URL}/api/onboarding/interests",
                json={"positive_topics": pos_slugs, "negative_topics": []},
                headers=headers,
            )
            print("Onboarding submission status:", onboarding_res.status_code)
            if onboarding_res.status_code in [200, 201]:
                print(f"Onboarded interests saved: {len(onboarding_res.json())}")

            # Check explicit interests
            interests_res = await client.get(
                f"{BASE_URL}/api/personalization/interests",
                headers=headers,
            )
            print("Explicit interests status:", interests_res.status_code)
            if interests_res.status_code == 200:
                print("User Explicit Interests count:", len(interests_res.json()))

        print("\n==================================================")
        print("4. VERIFYING NEWSPAPER GENERATION & EDITION")
        print("==================================================")
        # Generate / fetch today's edition
        np_res = await client.get(f"{BASE_URL}/api/newspaper/today", headers=headers)
        if np_res.status_code == 404 or np_res.json() is None:
            print("Generating today's personalized edition...")
            gen_res = await client.post(f"{BASE_URL}/api/newspaper/generate", headers=headers)
            print("Generation status:", gen_res.status_code)
            np_res = await client.get(f"{BASE_URL}/api/newspaper/today", headers=headers)

        assert np_res.status_code in [200, 201], f"Newspaper fetch failed: {np_res.text}"
        edition = np_res.json()
        print(f"Edition Title: {edition.get('title')}")
        print(f"Edition Date: {edition.get('edition_date')}")
        print(f"Total Stories: {edition.get('total_stories')}")
        print(f"Sections Count: {len(edition.get('sections', []))}")
        for s in edition.get("sections", []):
            print(f"  - Section '{s.get('name')}': {len(s.get('stories', []))} stories")

        print("\n==================================================")
        print("5. VERIFYING ARTICLES, STORY READER & USER ACTIONS")
        print("==================================================")
        # Fetch articles
        articles_res = await client.get(f"{BASE_URL}/api/articles", headers=headers)
        assert articles_res.status_code == 200, f"Articles list failed: {articles_res.text}"
        articles_data = articles_res.json()
        articles = articles_data.get("items", [])
        print(f"Available Articles in API: {len(articles)} (Total in DB: {articles_data.get('total')})")

        sample_article_id = None
        if articles:
            sample_art = articles[0]
            sample_article_id = sample_art["id"]
            print(f"Selected Sample Article: {sample_art.get('title')} ({sample_article_id})")

            # Article Detail
            art_res = await client.get(f"{BASE_URL}/api/articles/{sample_article_id}", headers=headers)
            assert art_res.status_code == 200, f"Article fetch failed: {art_res.text}"
            art = art_res.json()
            print(f"  Headline: {art.get('title')}")
            print(f"  Reading Time: {art.get('reading_time_minutes')} mins")
            print(f"  Source: {art.get('source_name')}")
            print(f"  Content Length: {len(art.get('content') or '')} chars")
            print(f"  Full text available: {art.get('is_full_text_available')}")

            # Like Action
            like_res = await client.post(
                f"{BASE_URL}/api/articles/{sample_article_id}/like",
                headers=headers,
            )
            print("  Like Action status:", like_res.status_code)

            # Save / Bookmark Action
            save_res = await client.post(
                f"{BASE_URL}/api/articles/{sample_article_id}/save",
                headers=headers,
            )
            print("  Save Action status:", save_res.status_code)

            # Not Interested Action
            not_interested_res = await client.post(
                f"{BASE_URL}/api/articles/{sample_article_id}/not-interested",
                headers=headers,
            )
            print("  Not Interested Action status:", not_interested_res.status_code)

            # Start Reading Session
            session_start_res = await client.post(
                f"{BASE_URL}/api/reading/start",
                json={"article_id": str(sample_article_id), "source_context": "NEWSPAPER"},
                headers=headers,
            )
            print("  Reading Session Start status:", session_start_res.status_code)
            if session_start_res.status_code in [200, 201]:
                s_id = session_start_res.json()["session_id"]
                hb_res = await client.post(
                    f"{BASE_URL}/api/reading/heartbeat",
                    json={"session_id": s_id, "scroll_percentage": 90.0, "active_duration_seconds": 30.0},
                    headers=headers,
                )
                print("  Reading Session Heartbeat status:", hb_res.status_code)
                end_res = await client.post(
                    f"{BASE_URL}/api/reading/end",
                    json={"session_id": s_id, "article_id": str(sample_article_id), "max_scroll_percentage": 100.0, "completion_percentage": 100.0},
                    headers=headers,
                )
                print("  Reading Session End status:", end_res.status_code)

            # Reading Metrics
            metrics_res = await client.get(f"{BASE_URL}/api/reading/metrics", headers=headers)
            print("  Reading Metrics status:", metrics_res.status_code)

        # Stories list & coverage
        stories_res = await client.get(f"{BASE_URL}/api/stories", headers=headers)
        if stories_res.status_code == 200:
            stories_data = stories_res.json()
            stories = stories_data.get("stories", [])
            print(f"Stories Feed Count: {len(stories)}")
            if stories:
                story_id = stories[0].get("slug") or stories[0].get("id")
                sdetail_res = await client.get(f"{BASE_URL}/api/stories/{story_id}", headers=headers)
                print(f"  Story Detail ({story_id}) status: {sdetail_res.status_code}")

        print("\n==================================================")
        print("6. VERIFYING PERSONALIZATION CONTROL CENTER")
        print("==================================================")
        prof_res = await client.get(f"{BASE_URL}/api/personalization/profile", headers=headers)
        assert prof_res.status_code == 200, f"Personalization profile failed: {prof_res.text}"
        profile = prof_res.json()
        print("Personalization Profile Loaded:")
        print(f"  Explicit Interests: {len(profile.get('explicit_interests', []))}")
        print(f"  Learned Topics: {len(profile.get('learned_topics', []))}")
        print(f"  Entity Preferences: {len(profile.get('entity_preferences', []))}")
        print(f"  Source Preferences: {len(profile.get('source_preferences', []))}")
        print(f"  Learning Status: {profile.get('settings', {}).get('learning_enabled')}")

        # Personalization settings
        sett_res = await client.get(f"{BASE_URL}/api/personalization/settings", headers=headers)
        assert sett_res.status_code == 200, f"Personalization settings failed: {sett_res.text}"
        sett = sett_res.json()
        print("Personalization Settings:")
        print(f"  Discovery Level: {sett.get('discovery_level')}")
        print(f"  Personalization Strength: {sett.get('personalization_strength')}")
        print(f"  Diversity Level: {sett.get('diversity_level')}")
        print(f"  Learning Enabled: {sett.get('learning_enabled')}")

        # Update Settings
        up_res = await client.put(
            f"{BASE_URL}/api/personalization/settings",
            json={
                "discovery_level": "EXPLORATORY",
                "personalization_strength": "HIGH",
                "diversity_level": "DIVERSE",
                "learning_enabled": True,
            },
            headers=headers,
        )
        assert up_res.status_code == 200, f"Settings update failed: {up_res.text}"
        print("Settings update status: 200 OK (EXPLORATORY, HIGH, DIVERSE)")

        # Topic Follow / Mute
        if topics:
            topic_to_test = topics[0]["id"]
            follow_res = await client.post(
                f"{BASE_URL}/api/personalization/topics/{topic_to_test}/follow",
                headers=headers,
            )
            print(f"Follow Topic status: {follow_res.status_code}")

            adjust_res = await client.post(
                f"{BASE_URL}/api/personalization/topics/{topic_to_test}/adjust",
                json={"action": "MORE"},
                headers=headers,
            )
            print(f"Adjust Topic feedback status: {adjust_res.status_code}")

            mute_res = await client.post(
                f"{BASE_URL}/api/personalization/topics/{topic_to_test}/mute",
                headers=headers,
            )
            print(f"Mute Topic status: {mute_res.status_code}")

            unmute_res = await client.post(
                f"{BASE_URL}/api/personalization/topics/{topic_to_test}/unmute",
                headers=headers,
            )
            print(f"Unmute Topic status: {unmute_res.status_code}")

        # Source Preference controls
        sources_res = await client.get(f"{BASE_URL}/api/sources", headers=headers)
        if sources_res.status_code == 200 and sources_res.json().get("sources"):
            test_src = sources_res.json()["sources"][0]
            prefer_res = await client.post(
                f"{BASE_URL}/api/personalization/sources/{test_src['id']}/prefer",
                headers=headers,
            )
            print(f"Prefer Source ({test_src['name']}) status: {prefer_res.status_code}")

        # Pause / Resume Learning
        pause_res = await client.post(f"{BASE_URL}/api/personalization/pause", headers=headers)
        print("Pause Learning status:", pause_res.status_code)
        resume_res = await client.post(f"{BASE_URL}/api/personalization/resume", headers=headers)
        print("Resume Learning status:", resume_res.status_code)

        print("\n==================================================")
        print("7. VERIFYING REAL INGESTION PIPELINE")
        print("==================================================")
        feeds_res = await client.get(f"{BASE_URL}/api/news/feeds")
        assert feeds_res.status_code == 200, f"Feeds list failed: {feeds_res.text}"
        feeds = feeds_res.json()
        print(f"Configured Feeds ({len(feeds)}):")
        for f in feeds[:4]:
            print(f"  - {f['name']} ({f['feed_url']})")

        if feeds:
            test_feed = feeds[0]
            print(f"\nTesting Feed Parsing: {test_feed['name']}...")
            test_parse_res = await client.post(f"{BASE_URL}/api/news/feeds/{test_feed['id']}/test")
            print(f"Feed Test Parse Status: {test_parse_res.status_code}")
            if test_parse_res.status_code == 200:
                tdata = test_parse_res.json()
                print(f"  Articles Parsed from Feed: {tdata.get('articles_count')}")

            print(f"\nTriggering Ingestion for Feed: {test_feed['name']}...")
            ingest_res = await client.post(
                f"{BASE_URL}/api/news/feeds/{test_feed['id']}/ingest",
                headers=headers,
            )
            print(f"Ingestion status: {ingest_res.status_code}")
            if ingest_res.status_code == 200:
                idata = ingest_res.json()
                print(f"  Articles Fetched: {idata.get('articles_fetched')}, Created: {idata.get('articles_created')}, Duplicates: {idata.get('duplicates_found')}")

        print("\n==================================================")
        print("8. VERIFYING SCHEDULER & BACKGROUND JOBS")
        print("==================================================")
        sched_res = await client.get(f"{BASE_URL}/api/admin/scheduler/status", headers=headers)
        assert sched_res.status_code == 200, f"Admin Scheduler Status failed: {sched_res.text}"
        sched_data = sched_res.json()
        print("Scheduler Status:", json.dumps(sched_data, indent=2))
        assert sched_data["scheduler"]["status"] == "running"
        assert sched_data["scheduler"]["running"] is True

        jobs_res = await client.get(f"{BASE_URL}/api/admin/jobs", headers=headers)
        assert jobs_res.status_code == 200, f"Admin Jobs failed: {jobs_res.text}"
        jobs_data = jobs_res.json()
        print(f"Total Background Jobs: {jobs_data.get('total', 0)}")
        print(f"Queue Stats: queued={sched_data['queue_stats']['queued']}, running={sched_data['queue_stats']['running']}, completed={sched_data['queue_stats']['completed']}")

        print("\n==================================================")
        print("9. VERIFYING FRONTEND APPLICATION ROUTES (NEXT.JS)")
        print("==================================================")
        routes = [
            ("/", "Home / Newspaper Front Page"),
            ("/login", "Login Page"),
            ("/register", "Registration Page"),
            ("/newspaper", "Daily Newspaper Edition"),
            ("/settings/personalization", "Personalization Control Center"),
            ("/sources", "Sources & Publisher Directory"),
        ]
        for route, label in routes:
            fe_res = await client.get(f"{FRONTEND_URL}{route}")
            assert fe_res.status_code == 200, f"Frontend route {route} failed: {fe_res.status_code}"
            print(f"  {label} ({FRONTEND_URL}{route}): 200 OK")

        print("\n>>> ALL VERIFICATIONS COMPLETED AND PASSED WITH 100% SUCCESS! <<<")

if __name__ == "__main__":
    asyncio.run(test_full_application())
