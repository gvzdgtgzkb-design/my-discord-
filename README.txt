╔══════════════════════════════════════════╗
║       Discord Store Bot — Setup Guide    ║
╚══════════════════════════════════════════╝

REQUIREMENTS
─────────────
• Python 3.10 or newer  →  https://python.org/downloads
• A Discord Bot Token   →  https://discord.com/developers/applications

─────────────────────────────────────────
STEP 1 — CREATE YOUR BOT TOKEN
─────────────────────────────────────────
1. Go to https://discord.com/developers/applications
2. Click "New Application" → give it a name
3. Go to "Bot" → click "Add Bot"
4. Under TOKEN → click "Copy"
5. Enable these Privileged Gateway Intents:
   ✅ SERVER MEMBERS INTENT
   ✅ MESSAGE CONTENT INTENT

─────────────────────────────────────────
STEP 2 — INVITE THE BOT TO YOUR SERVER
─────────────────────────────────────────
1. Go to OAuth2 → URL Generator
2. Scopes: ✅ bot  ✅ applications.commands
3. Bot Permissions: ✅ Send Messages ✅ Embed Links ✅ Read Messages/View Channels
4. Copy the URL and open it in your browser to invite the bot

─────────────────────────────────────────
STEP 3 — CONFIGURE YOUR TOKEN & OWNER ID
─────────────────────────────────────────
1. Copy ".env.example" and rename it to ".env"
2. Open ".env" and fill in both values:
   DISCORD_BOT_TOKEN=your_token_here
   OWNER_ID=your_discord_user_id_here

   To get your Discord ID:
   • Settings → Advanced → enable Developer Mode
   • Right-click your username anywhere → Copy User ID

   ⚠️ OWNER_ID locks /setup so ONLY you can become admin.
      Nobody else can run that command, ever.

─────────────────────────────────────────
STEP 4 — RUN THE BOT
─────────────────────────────────────────
• Windows: Double-click  run.bat
• Mac/Linux: Run  sh run.sh
• Manual:   pip install -r requirements.txt
            python bot.py

─────────────────────────────────────────
STEP 5 — FIRST TIME SETUP IN DISCORD
─────────────────────────────────────────
1. In any Discord channel, type:
   /setup user_id:YOUR_DISCORD_ID

   To get your Discord ID:
   • Enable Developer Mode: Settings → Advanced → Developer Mode
   • Right-click your name → "Copy User ID"

2. You are now the admin! Use /admin to manage everything.

─────────────────────────────────────────
ADMIN COMMANDS
─────────────────────────────────────────
/setup        — First-time setup (sets your Discord ID as admin)
/start        — Posts the store in the current channel
/admin        — Opens the full admin control panel
/addproduct   — Add a new product
/addprice     — Edit product prices
/addkey       — Add a key for a product
/removekey    — Remove a key from a product
/setpayment   — Set UPI ID or Binance Pay ID

─────────────────────────────────────────
ADDING PRODUCTS WITH CUSTOM EMOJIS
─────────────────────────────────────────
When adding a product, you can use Discord custom emojis:
• In the "Product Name" field: type ANTINA HOLO or add <:emoji:ID>
• In the "Custom Emoji" field: type  <:fire:123456789>  or  <a:glow:987654321>

To get a custom emoji ID:
• Type \:emojiname: in Discord (with a backslash)
• Copy the full <:name:ID> that appears

─────────────────────────────────────────
PURCHASE FLOW
─────────────────────────────────────────
1. User sees the store (posted by admin with /start)
2. User selects a product from dropdown
3. User sees product image, description, and prices
4. User selects duration (1 Day / 7 Days / 31 Days)
5. User confirms the order
6. User selects payment method (UPI or Binance Pay)
7. User sees payment details and clicks "✅ I Paid"
8. Admin receives a DM with order details + Approve/Reject buttons
9. If approved → user receives their key via DM
10. If rejected → user is notified

─────────────────────────────────────────
DATA FILES (auto-created in /data folder)
─────────────────────────────────────────
data/products.json  — All products
data/keys.json      — Keys per product
data/payments.json  — UPI & Binance IDs
data/orders.json    — Order history
data/config.json    — Admin IDs & settings

─────────────────────────────────────────
SUPPORT
─────────────────────────────────────────
Contact the seller on Discord for help.
