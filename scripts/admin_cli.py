#!/usr/bin/env python3
# CrownStar Admin CLI
import os, sys, argparse, json, datetime, subprocess, secrets, hmac, hashlib, base64
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from core.config import get_settings
from security.jwt import create_jwt, verify_jwt
from licensing.license_manager import LicenseManager
from multitenant.tenant.tenant_repo import get_tenant_repo
from multitenant.tenant.tenant_model import Tenant, TenantSettings
from ddd.repositories.repositories import SQLiteUserRepository, SQLiteConversationRepository
from ddd.value_object import UserId, Tier, ModelName

def get_license_manager(): return LicenseManager()
def get_tenant_repo_instance(): return get_tenant_repo()
def get_user_repo(): return SQLiteUserRepository()
def get_conv_repo(): return SQLiteConversationRepository()

def cmd_generate_license(args):
    lm = get_license_manager()
    key = lm.generate_license(args.email, args.tier, args.days_valid)
    print(f"License key for {args.email} ({args.tier}):")
    print(key)
    if args.output:
        with open(args.output, 'w') as f: f.write(key)
        print(f"Saved to {args.output}")

def cmd_validate_license(args):
    lm = get_license_manager()
    valid = lm.validate_license(args.license_key)
    if valid:
        print("License is VALID")
        payload = lm.decode_license(args.license_key)
        print(json.dumps(payload, indent=2))
    else:
        print("License is INVALID")

def cmd_create_tenant(args):
    repo = get_tenant_repo_instance()
    tenant = Tenant.create(args.name, args.subdomain, args.plan, args.created_by)
    if args.settings:
        with open(args.settings) as f:
            settings_dict = json.load(f)
            tenant.settings = TenantSettings(**settings_dict)
    repo.save(tenant)
    print(f"Tenant created: {tenant.tenant_id} - {tenant.name}")
    print(json.dumps(tenant.to_dict(), indent=2))

def cmd_list_tenants(args):
    repo = get_tenant_repo_instance()
    for t in repo.list_all(limit=args.limit):
        print(f"{t.tenant_id} | {t.name} | {t.plan} | {t.status}")

def cmd_backup(args):
    db_path = get_settings().DATABASE_URL.replace("sqlite+aiosqlite:///", "")
    if not os.path.exists(db_path):
        print("Database file not found.")
        return
    backup_file = args.output or f"backup_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.sqlite"
    import shutil
    shutil.copy2(db_path, backup_file)
    print(f"Backup saved to {backup_file}")

def cmd_restore(args):
    if not os.path.exists(args.file):
        print(f"Backup file {args.file} not found.")
        return
    db_path = get_settings().DATABASE_URL.replace("sqlite+aiosqlite:///", "")
    import shutil
    shutil.copy2(args.file, db_path)
    print(f"Database restored from {args.file}")

def cmd_create_user(args):
    repo = get_user_repo()
    from ddd.factories.factories import UserFactory
    user = UserFactory.create(args.username, args.email, tier=Tier(args.tier) if args.tier else None, model=ModelName(args.model) if args.model else None)
    if args.tenant_id:
        user.tenant_id = args.tenant_id
    repo.save(user)
    print(f"User created: {user.id.value} - {user.username}")

def cmd_status(args):
    from src.monitoring.health import check_health
    health = check_health()
    print("System Status:")
    print(json.dumps(health, indent=2))

def main():
    parser = argparse.ArgumentParser(description="CrownStar Admin CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    p = subparsers.add_parser("generate-license")
    p.add_argument("--email", required=True)
    p.add_argument("--tier", required=True, choices=["basic", "pro", "enterprise"])
    p.add_argument("--days-valid", type=int, default=365)
    p.add_argument("--output")
    p.set_defaults(func=cmd_generate_license)
    p = subparsers.add_parser("validate-license")
    p.add_argument("license_key")
    p.set_defaults(func=cmd_validate_license)
    p = subparsers.add_parser("create-tenant")
    p.add_argument("--name", required=True)
    p.add_argument("--subdomain")
    p.add_argument("--plan", default="free", choices=["free","basic","pro","enterprise"])
    p.add_argument("--created-by")
    p.add_argument("--settings")
    p.set_defaults(func=cmd_create_tenant)
    p = subparsers.add_parser("list-tenants")
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(func=cmd_list_tenants)
    p = subparsers.add_parser("backup")
    p.add_argument("--output")
    p.set_defaults(func=cmd_backup)
    p = subparsers.add_parser("restore")
    p.add_argument("file")
    p.set_defaults(func=cmd_restore)
    p = subparsers.add_parser("create-user")
    p.add_argument("--username", required=True)
    p.add_argument("--email", required=True)
    p.add_argument("--tier", default="free", choices=["free","basic","pro","enterprise"])
    p.add_argument("--model", default="deepseek_v2_lite")
    p.add_argument("--tenant-id")
    p.set_defaults(func=cmd_create_user)
    p = subparsers.add_parser("status")
    p.set_defaults(func=cmd_status)
    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
