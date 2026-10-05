import requests

res = requests.get("http://localhost:8000/api/approvals")
apps = res.json()
print("Pending Packages in Approvals Center:", len(apps))
for a in apps:
    job = a.get("job", {})
    match = a.get("match", {})
    rec = a.get("recruiter", {})
    print(f"• {job.get('title')} at {job.get('company')} - Match: {match.get('overall_score')}%")
    print(f"  Recruiter: {rec.get('name')} ({rec.get('title')}) - {rec.get('public_email') or 'LinkedIn direct link'}")
    print(f"  Approval ID: {a.get('approval_id')}")
