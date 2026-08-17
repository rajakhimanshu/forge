import os

base_dir = r"w:\The Office\Currently Working\TradingZone\TradingZoneOfficial\frontend"
out_file = r"w:\The Office\Currently Working\TradingZone\TradingZoneOfficial\frontend_audit.md"

files_to_append = [
    r"app\layout.tsx",
    r"app\page.tsx",
    r"app\(public)\login\page.tsx",
    r"app\(portal)\dashboard\page.tsx",
    r"app\lib\api.ts",
    r"app\lib\auth.ts",
    r"middleware.ts"
]

with open(out_file, "a", encoding="utf-8") as f:
    f.write("\n\n---\n\n### APPENDED CODEBASE FOR WINDSURF:\n")
    for file_path in files_to_append:
        full_path = os.path.join(base_dir, file_path)
        if os.path.exists(full_path):
            f.write(f"\n```tsx\n// === FILE: {file_path} ===\n")
            with open(full_path, "r", encoding="utf-8") as rf:
                f.write(rf.read())
            f.write("\n```\n")
print("Successfully appended codebase to frontend_audit.md")
