"""
Load Testing Suite for Customer Success FTE.

This module uses Locust to simulate realistic traffic patterns
and validate system performance under load.

Test Scenarios:
1. WebFormUser (weight=3) - Simulates customers submitting support forms
2. HealthCheckUser (weight=1) - Simulates monitoring/health checks

Usage:
    # Run Locust web UI
    locust -f production/tests/load_test.py --web-host=0.0.0.0 --web-port=8089

    # Run headless (no UI) with specific user count and duration
    locust -f production/tests/load_test.py --headless -u 50 -r 10 --run-time 5m

    # Run with custom host
    locust -f production/tests/load_test.py --host=http://localhost:8000 --headless -u 100 -r 20 --run-time 10m

    # Run with CSV output for analysis
    locust -f production/tests/load_test.py --headless -u 50 -r 10 --run-time 5m --csv=results/load_test

Requirements:
    pip install locust
"""

import random
import string
import time
import json
from datetime import datetime
from typing import Dict, Any, List

from locust import HttpUser, task, between, events
from locust.runners import MasterRunner, WorkerRunner

# =============================================================================
# TEST DATA GENERATORS
# =============================================================================

# Realistic test data pools
FIRST_NAMES = [
    "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda",
    "William", "Elizabeth", "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Lisa", "Daniel", "Nancy",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Donald", "Ashley",
    "Steven", "Dorothy", "Paul", "Kimberly", "Andrew", "Emily", "Joshua", "Donna",
    "Kenneth", "Michelle", "Kevin", "Carol", "Brian", "Amanda", "George", "Melissa",
    "Timothy", "Deborah", "Ronald", "Stephanie", "Edward", "Rebecca", "Jason", "Sharon",
    "Jeffrey", "Laura", "Ryan", "Cynthia", "Jacob", "Kathleen", "Gary", "Amy",
    "Nicholas", "Angela", "Eric", "Shirley", "Jonathan", "Anna", "Stephen", "Brenda",
    "Larry", "Pamela", "Justin", "Emma", "Scott", "Nicole", "Brandon", "Helen",
    "Benjamin", "Samantha", "Samuel", "Katherine", "Raymond", "Christine", "Gregory", "Debra",
    "Frank", "Rachel", "Alexander", "Carolyn", "Patrick", "Janet", "Jack", "Catherine",
    "Dennis", "Maria", "Jerry", "Heather", "Tyler", "Diane",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas",
    "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson", "White",
    "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker", "Young",
    "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
    "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
    "Carter", "Roberts", "Gomez", "Phillips", "Evans", "Turner", "Diaz", "Parker",
    "Cruz", "Edwards", "Collins", "Reyes", "Stewart", "Morris", "Morales", "Murphy",
    "Cook", "Rogers", "Gutierrez", "Ortiz", "Morgan", "Cooper", "Peterson", "Bailey",
    "Reed", "Kelly", "Howard", "Ramos", "Kim", "Cox", "Ward", "Richardson",
    "Watson", "Brooks", "Chavez", "Wood", "James", "Bennett", "Gray", "Mendoza",
    "Ruiz", "Hughes", "Price", "Alvarez", "Castillo", "Sanders", "Patel", "Myers",
]

COMPANIES = [
    "Acme Corp", "TechStart Inc", "Global Solutions", "Innovate Labs", "DataFlow Systems",
    "CloudNine Services", "NextGen Technologies", "PrimeSoft", "BlueSky Analytics", "Quantum Dynamics",
    "Apex Industries", "Stellar Networks", "FusionWorks", "Pinnacle Group", "Horizon Digital",
    "Catalyst Ventures", "Synergy Partners", "Velocity Systems", "Nexus Technologies", "Atlas Solutions",
    None, None, None,  # 30% chance of no company
]

SUBJECT_TEMPLATES = [
    "Unable to {action} my account",
    "Question about {feature} functionality",
    "Error when trying to {action}",
    "How do I {action}?",
    "Issue with {feature} not working",
    "Billing inquiry for {month}",
    "Request to {action} my subscription",
    "Bug report: {feature} crashes",
    "Need help with {feature} setup",
    "Password reset not working",
    "Feature request: {feature}",
    "Integration with {service} not syncing",
    "Performance issue with {feature}",
    "Cannot access {feature} after update",
    "Refund request for order #{order_id}",
]

ACTIONS = [
    "access", "login to", "update", "reset", "configure", "export", "import",
    "sync", "connect", "authorize", "verify", "activate", "deactivate", "cancel",
]

FEATURES = [
    "dashboard", "reporting", "notifications", "API", "webhooks", "integrations",
    "user management", "billing", "search", "filters", "export", "analytics",
    "automation", "workflows", "templates", "custom fields", "tags",
]

SERVICES = [
    "Slack", "Zapier", "Salesforce", "HubSpot", "Stripe", "Google Sheets",
    "Jira", "GitHub", "Notion", "Trello", "Asana", "Monday.com",
]

DESCRIPTION_TEMPLATES = [
    "Hi, I'm having trouble with {feature}. When I try to {action}, I get an error message saying '{error}'. "
    "This started happening {timeframe}. I've tried {attempt} but it didn't help. "
    "Can you please assist? My account email is {email}. Thanks!",

    "Hello, I need help with {feature}. I'm trying to {action} but it's not working as expected. "
    "The issue is that {detail}. I've been using your product for {duration} and haven't had this problem before. "
    "Please let me know how to resolve this. Thank you.",

    "Hey there, I'm experiencing an issue with {feature}. Every time I {action}, the system {behavior}. "
    "I've attached screenshots of the error. My browser is {browser} and I'm on {os}. "
    "This is affecting my workflow significantly. Urgent help would be appreciated.",

    "Good morning, I have a question about {feature}. I want to {action} but I'm not sure how to proceed. "
    "I've checked the documentation but couldn't find clear instructions. "
    "Could you provide step-by-step guidance? Thanks in advance!",

    "Hi support team, I noticed an issue with my {feature} settings. After the recent update, "
    "{detail}. This is causing problems with my {impact}. "
    "I need this resolved as soon as possible as it's affecting my team's productivity. "
    "Please advise on next steps.",
]

ERROR_MESSAGES = [
    "Something went wrong. Please try again.",
    "Invalid credentials. Please check your input.",
    "Session expired. Please log in again.",
    "Rate limit exceeded. Please wait and try again.",
    "Internal server error. Our team has been notified.",
    "Connection timeout. Please check your internet connection.",
    "Access denied. You don't have permission to perform this action.",
    "Resource not found. The item you're looking for may have been deleted.",
    "Payment failed. Please check your billing information.",
    "Service temporarily unavailable. Please try again later.",
]

TIMEFRAMES = [
    "yesterday", "this morning", "a few hours ago", "after the latest update",
    "since last week", "about 30 minutes ago", "earlier today", "over the weekend",
]

ATTEMPTS = [
    "clearing my cache and cookies", "restarting my browser", "trying a different browser",
    "logging out and back in", "checking my internet connection", "updating my password",
    "disabling my ad blocker", "using incognito mode",
]

BROWSERS = [
    "Chrome 120", "Firefox 121", "Safari 17", "Edge 120", "Opera 105",
]

OPERATING_SYSTEMS = [
    "Windows 11", "macOS Sonoma", "Ubuntu 22.04", "Windows 10", "macOS Ventura",
]

DURATIONS = [
    "about 6 months", "over a year", "a few weeks", "3 months",
    "since the beginning", "a couple of years", "recently",
]

IMPACTS = [
    "daily reports", "client communications", "team collaboration",
    "data exports", "automated workflows", "project deadlines",
]

CATEGORIES = ["technical", "billing", "account", "feature_request", "bug_report", "general"]
PRIORITIES = ["low", "medium", "high", "critical"]
PRIORITY_WEIGHTS = [0.2, 0.5, 0.25, 0.05]  # 50% medium, 25% high, 20% low, 5% critical


def generate_random_email(name: str) -> str:
    """Generate realistic random email."""
    domains = ["gmail.com", "yahoo.com", "outlook.com", "company.com", "example.org", "mail.com"]
    name_part = name.lower().replace(" ", ".")
    suffix = random.randint(1, 999)
    return f"{name_part}{suffix}@{random.choice(domains)}"


def generate_realistic_subject() -> str:
    """Generate realistic support request subject."""
    template = random.choice(SUBJECT_TEMPLATES)
    return template.format(
        action=random.choice(ACTIONS),
        feature=random.choice(FEATURES),
        month=random.choice(["January", "February", "March", "April", "May", "June"]),
        order_id=random.randint(10000, 99999),
    )


def generate_realistic_description(email: str) -> str:
    """Generate realistic support request description."""
    template = random.choice(DESCRIPTION_TEMPLATES)
    return template.format(
        feature=random.choice(FEATURES),
        action=random.choice(ACTIONS),
        error=random.choice(ERROR_MESSAGES),
        timeframe=random.choice(TIMEFRAMES),
        attempt=random.choice(ATTEMPTS),
        email=email,
        detail=random.choice([
            "the page loads but shows incomplete data",
            "I get redirected to an error page",
            "nothing happens when I click the button",
            "the data doesn't save properly",
            "I see a blank screen",
            "the system is very slow",
            "notifications aren't working",
        ]),
        duration=random.choice(DURATIONS),
        browser=random.choice(BROWSERS),
        os=random.choice(OPERATING_SYSTEMS),
        behavior=random.choice([
            "freezes for about 30 seconds",
            "shows an error message",
            "logs me out unexpectedly",
            "duplicates my entries",
            "loses my progress",
        ]),
        impact=random.choice(IMPACTS),
    )


def generate_form_submission() -> Dict[str, Any]:
    """Generate a complete realistic support form submission."""
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    full_name = f"{first_name} {last_name}"
    email = generate_random_email(full_name)
    company = random.choice(COMPANIES)

    submission = {
        "name": full_name,
        "email": email,
        "subject": generate_realistic_subject(),
        "description": generate_realistic_description(email),
        "category": random.choice(CATEGORIES),
        "priority": random.choices(PRIORITIES, weights=PRIORITY_WEIGHTS, k=1)[0],
    }

    # Optional fields
    if company:
        submission["company"] = company
    
    if random.random() < 0.3:  # 30% include phone
        submission["phone"] = f"+1{random.randint(2000000000, 9999999999)}"
    
    if random.random() < 0.2:  # 20% include order ID
        submission["order_id"] = f"ORD-{random.randint(10000, 99999)}"

    return submission


# =============================================================================
# LOCUST EVENT HANDLERS
# =============================================================================


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when load test starts."""
    print("\n" + "=" * 80)
    print("LOAD TEST STARTED")
    print("=" * 80)
    print(f"Target Host: {environment.host}")
    print(f"Start Time: {datetime.now().isoformat()}")
    print("=" * 80)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when load test stops."""
    print("\n" + "=" * 80)
    print("LOAD TEST COMPLETED")
    print("=" * 80)
    print(f"End Time: {datetime.now().isoformat()}")
    print("=" * 80)
    
    # Print summary statistics
    stats = environment.runner.stats
    print("\nREQUEST STATISTICS:")
    print(f"Total Requests: {stats.total.num_requests}")
    print(f"Total Failures: {stats.total.num_failures}")
    print(f"Average Response Time: {stats.total.avg_response_time:.2f}ms")
    print(f"Median Response Time: {stats.total.median_response_time}ms")
    print(f"95th Percentile: {stats.total.get_response_time_percentile(0.95)}ms")
    print(f"99th Percentile: {stats.total.get_response_time_percentile(0.99)}ms")
    print(f"Requests/sec: {stats.total.current_rps:.2f}")
    print(f"Failures/sec: {stats.total.current_fail_per_sec:.2f}")
    print("=" * 80)


@events.report_to_master.add_listener
def on_report_to_master(environment, is_worker, data, **kwargs):
    """Add custom data to reports sent to master."""
    if is_worker:
        data["custom_metrics"] = {
            "test_type": "customer_success_fte_load_test",
            "timestamp": datetime.now().isoformat(),
        }


@events.report_from_master.add_listener
def on_report_from_master(environment, is_worker, data, **kwargs):
    """Receive custom data from master."""
    if is_worker and "custom_metrics" in data:
        print(f"Received master data: {data['custom_metrics']}")


# =============================================================================
# USER CLASS 1: WEB FORM USER (Weight = 3)
# =============================================================================


class WebFormUser(HttpUser):
    """
    Simulates customers submitting support forms.
    
    This is the most common user type (weight=3) representing
    real customers seeking help through the web form.
    
    Behavior:
    - Submits support form with realistic data
    - Optionally checks ticket status after submission
    - Waits 2-10 seconds between actions
    """
    
    # Wait 2-10 seconds between tasks
    wait_time = between(2, 10)
    
    # Weight: 3x more likely than HealthCheckUser
    weight = 3
    
    def on_start(self):
        """Called when a simulated user starts."""
        self.submitted_tickets = []
        self.user_data = generate_form_submission()
    
    @task(5)
    def submit_support_form(self):
        """
        Submit a support form with realistic random data.
        
        This is the primary task simulating real customer behavior.
        """
        # Generate fresh submission data
        submission = generate_form_submission()
        
        with self.client.post(
            "/support/submit",
            json=submission,
            name="/support/submit",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get("success") and data.get("ticket_id"):
                        self.submitted_tickets.append(data["ticket_id"])
                        response.success()
                    else:
                        response.failure(f"Unexpected response: {data}")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            elif response.status_code == 422:
                # Validation error - might be expected with bad data
                response.failure(f"Validation error: {response.text}")
            elif response.status_code == 429:
                # Rate limited - expected under high load
                response.success()  # Rate limiting is working as designed
            else:
                response.failure(f"Unexpected status: {response.status_code}")
    
    @task(2)
    def check_ticket_status(self):
        """
        Check status of a previously submitted ticket.
        
        Simulates customers checking their ticket status.
        """
        if not self.submitted_tickets:
            return  # No tickets to check
        
        ticket_id = random.choice(self.submitted_tickets)
        email = self.user_data["email"]
        
        with self.client.get(
            f"/support/status/{ticket_id}",
            params={"email": email},
            name="/support/status/[ticket_id]",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 404:
                response.failure("Ticket not found")
            else:
                response.failure(f"Unexpected status: {response.status_code}")
    
    @task(1)
    def submit_invalid_form(self):
        """
        Submit an invalid form to test validation.
        
        Simulates users making mistakes or testing boundaries.
        """
        invalid_submissions = [
            {"name": "", "email": "invalid", "subject": "X", "description": "X"},
            {"name": "Test", "email": "not-an-email", "subject": "Test", "description": "This is a test description for validation."},
            {"name": "Test", "email": "test@test.com", "subject": "Test", "description": "X", "honeypot": "spam"},
        ]
        
        submission = random.choice(invalid_submissions)
        
        with self.client.post(
            "/support/submit",
            json=submission,
            name="/support/submit [invalid]",
            catch_response=True,
        ) as response:
            if response.status_code == 422:
                response.success()  # Validation working correctly
            elif response.status_code == 200:
                response.failure("Should have rejected invalid data")
            else:
                response.failure(f"Unexpected status: {response.status_code}")


# =============================================================================
# USER CLASS 2: HEALTH CHECK USER (Weight = 1)
# =============================================================================


class HealthCheckUser(HttpUser):
    """
    Simulates monitoring systems and health checks.
    
    This user type represents:
    - Kubernetes liveness/readiness probes
    - Monitoring systems (Prometheus, Datadog, etc.)
    - Admin dashboard health checks
    
    Behavior:
    - Checks /health endpoint
    - Checks /metrics endpoints
    - Waits 5-15 seconds between checks
    """
    
    # Wait 5-15 seconds between tasks
    wait_time = between(5, 15)
    
    # Weight: 1x (less frequent than form submissions)
    weight = 1
    
    @task(3)
    def check_health(self):
        """
        Check the health endpoint.
        
        Simulates Kubernetes probes and monitoring systems.
        """
        with self.client.get(
            "/health",
            name="/health",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get("status") == "healthy":
                        response.success()
                    else:
                        response.failure(f"Unhealthy status: {data.get('status')}")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"Unexpected status: {response.status_code}")
    
    @task(2)
    def check_readiness(self):
        """
        Check the readiness endpoint.
        
        Simulates Kubernetes readiness probes.
        """
        with self.client.get(
            "/ready",
            name="/ready",
            catch_response=True,
        ) as response:
            if response.status_code in [200, 503]:
                response.success()  # Both are valid responses
            else:
                response.failure(f"Unexpected status: {response.status_code}")
    
    @task(1)
    def check_liveness(self):
        """
        Check the liveness endpoint.
        
        Simulates Kubernetes liveness probes.
        """
        with self.client.get(
            "/live",
            name="/live",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")
    
    @task(2)
    def check_channel_metrics(self):
        """
        Check metrics for each channel.
        
        Simulates monitoring dashboards pulling metrics.
        """
        channels = ["email", "whatsapp", "web_form"]
        
        for channel in channels:
            with self.client.get(
                f"/metrics/channels/{channel}",
                name="/metrics/channels/[channel]",
                catch_response=True,
            ) as response:
                if response.status_code in [200, 404, 503]:
                    response.success()  # All acceptable responses
                else:
                    response.failure(f"Unexpected status: {response.status_code}")
    
    @task(1)
    def check_metrics_summary(self):
        """
        Check overall metrics summary.
        
        Simulates admin dashboard loading summary metrics.
        """
        with self.client.get(
            "/metrics/summary",
            name="/metrics/summary",
            catch_response=True,
        ) as response:
            if response.status_code in [200, 401, 403]:
                response.success()  # Auth errors expected without API key
            else:
                response.failure(f"Unexpected status: {response.status_code}")


# =============================================================================
# LOAD TEST PROFILES
# =============================================================================


# Profile definitions for different load scenarios
LOAD_PROFILES = {
    "smoke": {
        "description": "Smoke test - minimal load to verify system works",
        "users": 5,
        "spawn_rate": 1,
        "run_time": "2m",
    },
    "normal": {
        "description": "Normal load - typical daily traffic",
        "users": 50,
        "spawn_rate": 5,
        "run_time": "10m",
    },
    "peak": {
        "description": "Peak load - busy hour simulation",
        "users": 200,
        "spawn_rate": 20,
        "run_time": "15m",
    },
    "stress": {
        "description": "Stress test - find breaking point",
        "users": 500,
        "spawn_rate": 50,
        "run_time": "20m",
    },
    "soak": {
        "description": "Soak test - long duration for memory leaks",
        "users": 100,
        "spawn_rate": 10,
        "run_time": "2h",
    },
}


def print_load_profiles():
    """Print available load test profiles."""
    print("\n" + "=" * 80)
    print("AVAILABLE LOAD TEST PROFILES")
    print("=" * 80)
    for name, profile in LOAD_PROFILES.items():
        print(f"\n{name.upper()}:")
        print(f"  Description: {profile['description']}")
        print(f"  Users: {profile['users']}")
        print(f"  Spawn Rate: {profile['spawn_rate']} users/sec")
        print(f"  Duration: {profile['run_time']}")
    print("=" * 80)


# =============================================================================
# MAIN (for running profiles)
# =============================================================================


if __name__ == "__main__":
    import subprocess
    import sys
    
    print("\nCustomer Success FTE - Load Testing Suite")
    print("=" * 80)
    
    if len(sys.argv) > 1:
        profile_name = sys.argv[1].lower()
        
        if profile_name == "list":
            print_load_profiles()
            sys.exit(0)
        
        if profile_name not in LOAD_PROFILES:
            print(f"Unknown profile: {profile_name}")
            print(f"Available profiles: {', '.join(LOAD_PROFILES.keys())}")
            print("Use 'list' to see all profiles")
            sys.exit(1)
        
        profile = LOAD_PROFILES[profile_name]
        
        print(f"\nRunning profile: {profile_name.upper()}")
        print(f"Description: {profile['description']}")
        print(f"Users: {profile['users']}")
        print(f"Spawn Rate: {profile['spawn_rate']}")
        print(f"Duration: {profile['run_time']}")
        print("\nStarting Locust...")
        
        # Build Locust command
        cmd = [
            "locust",
            "-f", __file__,
            "--headless",
            "-u", str(profile["users"]),
            "-r", str(profile["spawn_rate"]),
            "--run-time", profile["run_time"],
            "--host", "http://localhost:8000",
            "--csv", f"results/load_test_{profile_name}",
        ]
        
        print(f"\nCommand: {' '.join(cmd)}\n")
        
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Load test failed: {e}")
            sys.exit(1)
        except KeyboardInterrupt:
            print("\nLoad test interrupted by user")
            sys.exit(0)
    else:
        print("Usage: python load_test.py <profile>")
        print("Profiles: smoke, normal, peak, stress, soak")
        print("Use 'list' to see all profiles")
        print("\nOr run Locust directly:")
        print("  locust -f production/tests/load_test.py --web-host=0.0.0.0 --web-port=8089")
