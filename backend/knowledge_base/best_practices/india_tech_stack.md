# India-Appropriate Tech Stack for Student Projects 2026

## Payments
Razorpay: Best for India. Supports UPI, NEFT, IMPS, cards.
Free to set up. 2% per transaction. No monthly fee.
Cashfree: Alternative. 1.99% per transaction. Better for subscriptions.
NEVER use Stripe for India — limited UPI support, INR conversion fees.

## SMS / OTP
Fast2SMS: 0.15 INR per SMS. 50 free credits on signup.
msg91: 0.18 INR per SMS. Better delivery rates for Tier-2 cities.
NEVER use Twilio for India — costs 10x more than local providers.

## Free Hosting (No Credit Card)
Railway: 5 USD/month free credit. Node.js and Python both supported.
Render: Free tier available. 512MB RAM. Sleeps after 15min inactivity.
Cyclic: Free forever for Node.js apps. Good for student projects.
Vercel: Free forever for frontend React/Next.js apps.

## Free Databases
MongoDB Atlas: 512MB free forever. Good for flexible schemas.
Supabase: 500MB PostgreSQL free. Also includes auth and storage.
Turso: SQLite edge DB. 500MB free. Good for simple apps.

## File Storage
Cloudinary: 25GB free, 25000 transformations/month. Best for images.
Supabase Storage: 1GB free. Good when already using Supabase DB.

## Authentication
JWT (jsonwebtoken): Free, no service needed. Self-managed tokens.
Supabase Auth: Free, includes OTP, magic link. Best for quick auth setup.
Firebase Auth: Free, 10k authentications/month. Good for OTP login.
