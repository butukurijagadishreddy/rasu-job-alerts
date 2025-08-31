"""
Simple Job Monitor - No .env dependencies
"""

import requests
import re
import json
import time
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
from datetime import datetime
import schedule

# Configuration from environment variables (Railway) or fallback (local)
import os
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8394272919:AAHWv_m5rDjpP5IfqA4PLuUgzfdbUGiI2_Q')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '6632953767')
DICE_USERNAME = os.environ.get('DICE_USERNAME', 'rasagnaarja3@gmail.com')
DICE_PASSWORD = os.environ.get('DICE_PASSWORD', 'Rasa@1234')

JOB_TITLES = ['data+engineer', 'etl+developer', 'big+data+engineer', 'cloud+data+engineer']
CHECK_INTERVAL = 15  # minutes

class RasuJobBot:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.seen_jobs = set()
        print("🤖 Rasu Job Monitor - C2C/C2H Data Engineer Jobs")
        print("💼 Contract opportunities only")
        print("📍 USA only, last 24 hours")
        print(f"⏱️ Checking every {CHECK_INTERVAL} minutes")
        print("=" * 50)
    
    def login_to_dice(self):
        """Login to Dice"""
        try:
            print("🔐 Logging into Dice...")
            
            login_url = "https://www.dice.com/dashboard/login"
            response = self.session.get(login_url)
            
            soup = BeautifulSoup(response.content, 'html.parser')
            csrf_token = None
            csrf_input = soup.find('input', {'name': '_token'})
            if csrf_input:
                csrf_token = csrf_input.get('value')
            
            login_data = {
                'email': DICE_USERNAME,
                'password': DICE_PASSWORD
            }
            if csrf_token:
                login_data['_token'] = csrf_token
            
            response = self.session.post(login_url, data=login_data)
            
            if response.status_code == 200:
                print("✅ Dice login successful")
                return True
            else:
                print(f"❌ Login failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Login error: {e}")
            return False
    
    def get_job_details(self, job_url):
        """Get job details"""
        try:
            response = self.session.get(job_url)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Get employment type chip
                employment_chip = soup.select_one('[data-cy="employmentDetails"] span')
                employment_type = ""
                if employment_chip:
                    employment_type = employment_chip.get_text().lower()
                
                # Get job description
                desc_elem = soup.select_one('[data-cy="jobDescription"]')
                description = desc_elem.get_text() if desc_elem else soup.get_text()
                
                combined_text = f"{employment_type} {description}".lower()
                
                return {'description': combined_text, 'employment_type': employment_type}
            
            return None
                
        except Exception as e:
            return None
    
    def is_c2c_or_c2h_job(self, job_details):
        """Check if job is C2C or C2H"""
        if not job_details:
            return False
        
        text = job_details.get('description', '')
        
        # EXCLUDE
        exclude_terms = [
            'full time', 'fulltime', 'full-time',
            'w2 only', 'w2 candidates', 'w2 required',
            'permanent', 'employee', 'fte',
            'contract - w2', 'contract - independent',
            'independent contractor', 'direct hire',
            'no contractors', 'employees only'
        ]
        
        if any(term in text for term in exclude_terms):
            return False
        
        # ONLY ACCEPT
        accept_terms = [
            'c2c', 'corp to corp', 'corp-to-corp', 'corp 2 corp',
            'contract to contract', 'contract-to-contract', 'contract 2 contract',
            'c2h', 'contract to hire', 'contract-to-hire'
        ]
        
        return any(term in text for term in accept_terms)
    
    def search_dice_jobs(self):
        """Search Dice for jobs"""
        all_jobs = []
        
        try:
            for term in JOB_TITLES:
                search_url = f"https://www.dice.com/jobs?q={term}&location=United+States&radius=30&radiusUnit=mi&pageSize=50&filters.postedDate=ONE"
                
                print(f"🔍 Searching: {term.replace('+', ' ')}")
                response = self.session.get(search_url)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    engineer_links = soup.find_all('a', string=re.compile(r'engineer|developer', re.IGNORECASE))
                    
                    print(f"Found {len(engineer_links)} potential jobs")
                    
                    for link in engineer_links[:15]:  # Limit for speed
                        try:
                            job_title = link.get_text(strip=True)
                            job_url = link.get('href', '')
                            
                            if any(skip in job_title.lower() for skip in ['search', 'recommended']):
                                continue
                            
                            if not any(keyword in job_title.lower() for keyword in ['data', 'etl', 'big data', 'cloud']):
                                continue
                            
                            if not job_url.startswith('http'):
                                job_url = f"https://www.dice.com{job_url}"
                            
                            print(f"  🔍 Checking: {job_title[:40]}...")
                            job_details = self.get_job_details(job_url)
                            
                            if job_details and self.is_c2c_or_c2h_job(job_details):
                                job = {
                                    'title': job_title,
                                    'company': 'Contract Opportunity',
                                    'location': 'Remote/USA',
                                    'url': job_url,
                                    'source': 'Dice'
                                }
                                
                                all_jobs.append(job)
                                print(f"✅ C2C/C2H: {job_title}")
                            else:
                                print(f"❌ W2/Full-time: {job_title[:40]}")
                            
                        except Exception as e:
                            continue
                
                time.sleep(3)
                
        except Exception as e:
            print(f"❌ Search error: {e}")
        
        return all_jobs
    
    def send_telegram(self, jobs):
        """Send Telegram notification"""
        try:
            message = f"🎯 *{len(jobs)} New C2C/C2H Jobs!*\n\n"
            
            for i, job in enumerate(jobs, 1):
                message += f"{i}. *{job['title']}*\n"
                message += f"   🏢 {job['company']}\n"
                message += f"   📍 {job['location']}\n"
                message += f"   [Apply Now]({job['url']})\n\n"
            
            message += "🔍 *Only C2C, C2H, Corp-to-Corp, Contract-to-Hire*"
            
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                'chat_id': TELEGRAM_CHAT_ID,
                'text': message,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': True
            }
            
            response = requests.post(url, data=payload)
            return response.status_code == 200
                
        except Exception as e:
            print(f"❌ Telegram error: {e}")
            return False
    
    def run_search(self):
        """Run job search"""
        print(f"\n🔍 Check - {datetime.now().strftime('%H:%M:%S')}")
        
        if not self.login_to_dice():
            return
        
        jobs = self.search_dice_jobs()
        
        if jobs:
            new_jobs = []
            for job in jobs:
                job_id = f"{job['title']}_{job['company']}"
                if job_id not in self.seen_jobs:
                    new_jobs.append(job)
                    self.seen_jobs.add(job_id)
            
            if new_jobs:
                print(f"🎉 {len(new_jobs)} NEW jobs!")
                self.send_telegram(new_jobs)
        else:
            print("❌ No C2C/C2H jobs found")
    
    def start_monitoring(self):
        """Start monitoring"""
        # Send startup notification
        startup_msg = f"🤖 *Rasu Job Bot Started!*\n\nMonitoring C2C/C2H Data Engineer jobs every {CHECK_INTERVAL} minutes"
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': startup_msg, 'parse_mode': 'Markdown'}
        requests.post(url, data=payload)
        
        self.run_search()
        
        schedule.every(CHECK_INTERVAL).minutes.do(self.run_search)
        
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)
            except KeyboardInterrupt:
                print("🛑 Stopped")
                break

def main():
    bot = RasuJobBot()
    bot.start_monitoring()

if __name__ == "__main__":
    main()
