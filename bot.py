import re
import io
import segno
import discord
from discord import app_commands
from discord.ui import View, Button, Select, Modal, TextInput

from settings import BOT_TOKEN, OWNER_IDS
from config import config, is_admin, add_admin, save_config
from products import (
    get_all_products, find_product, add_product,
    update_product_prices, set_product_image, remove_product, format_price
)
from payments import payment_config, set_binance, get_binance, set_upi_qr_url, get_upi_qr_url
from keys import add_key, remove_key, pop_key, count_keys, get_keys
from orders import create_order, get_order, approve_order, reject_order

if not BOT_TOKEN:
    raise RuntimeError("Set DISCORD_BOT_TOKEN in your .env file.")
if not OWNER_IDS:
    raise RuntimeError("OWNER_IDS must be set in settings.py")

TOKEN = BOT_TOKEN

# ─── Emoji IDs (bot resolves these to proper names at runtime) ────────────────
_EID_PRODUCT  = 1484006620466909254   # <:1455376139169173565:...>
_EID_DURATION = 1466466609005596908   # <a:config:...>
_EID_AMOUNT   = 1483951052855181422   # <:989206073988755526:...>
_EID_CONFIRM  = 1466465930522656841   # <:hyperapps29:...>
_EID_PAYMENT  = 1333002233041784886   # <a:blackcartao:...>
_EID_PRICE    = 1466466495801331782   # <:price:...>
_EID_PAID     = 1466466203341029396   # <a:confirmar:...>

# Unicode fallbacks shown if the bot can't find the emoji in its cache
_FB: dict[int, str] = {
    _EID_PRODUCT:  "📦",
    _EID_DURATION: "⏳",
    _EID_AMOUNT:   "💰",
    _EID_CONFIRM:  "🧾",
    _EID_PAYMENT:  "💳",
    _EID_PRICE:    "💲",
    _EID_PAID:     "✅",
}


# ─────────────────────────────────────────────
#  BOT SETUP
# ─────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True


class StoreBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()


bot = StoreBot()


# ─────────────────────────────────────────────
#  EMOJI HELPERS
# ─────────────────────────────────────────────

def _e(emoji_id: int) -> str:
    """
    Look up a custom emoji by ID in the bot's guild cache.
    Returns the proper <:name:id> string Discord will render.
    Falls back to a unicode emoji if not found.
    """
    emoji_obj = bot.get_emoji(emoji_id)
    if emoji_obj:
        return str(emoji_obj)
    return _FB.get(emoji_id, "")


def resolve_product_emoji(raw: str) -> str:
    """
    Resolve a product emoji stored in products.json.
    Extracts the last Discord snowflake ID from the string and looks it up
    in the bot's cache so we always get a properly-named <:name:id> tag.
    Returns empty string if the emoji can't be resolved.
    """
    raw = raw.strip()
    if not raw:
        return ""
    # Already a standard animated emoji like <a:name:id> where name is text
    m = re.match(r"<(a?):([a-zA-Z_]\w*):(\d+)>", raw)
    if m:
        # Name is valid (starts with a letter) — look up to confirm, or use as-is
        eid = int(m.group(3))
        emoji_obj = bot.get_emoji(eid)
        return str(emoji_obj) if emoji_obj else raw

    # Extract all snowflake IDs from the string (numeric IDs 15-20 digits)
    ids = re.findall(r"\d{15,20}", raw)
    # Try each ID — the actual emoji ID is usually the LAST number in <:name:id>
    for id_str in reversed(ids):
        emoji_obj = bot.get_emoji(int(id_str))
        if emoji_obj:
            return str(emoji_obj)

    # Can't resolve — return empty so we don't show broken text
    return ""


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def get_admin_ids() -> list[int]:
    return config.get("admin_ids", [])


def check_admin(interaction: discord.Interaction) -> bool:
    return is_admin(interaction.user.id)


def _msg_is_ephemeral(interaction: discord.Interaction) -> bool:
    try:
        return bool(interaction.message and interaction.message.flags.ephemeral)
    except Exception:
        return False


async def _respond(interaction: discord.Interaction, *, embed, view=None, attachments=None):
    """Edit in-place if ephemeral, otherwise send new ephemeral reply."""
    if _msg_is_ephemeral(interaction):
        kwargs: dict = {"embed": embed, "view": view}
        if attachments is not None:
            kwargs["attachments"] = attachments
        await interaction.response.edit_message(**kwargs)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# ─────────────────────────────────────────────
#  EMBEDS
# ─────────────────────────────────────────────

def store_embed() -> discord.Embed:
    products = get_all_products()
    embed = discord.Embed(
        title="╔══════════════════════════╗\n        🏪  PREMIUM  STORE        \n╚══════════════════════════╝",
        description=(
            "> 🛡️ **All purchases are manually verified by admins.**\n"
            "> ⚡ Instant key delivery after approval.\n"
            "> 💬 Need help? Contact support in this server.\n"
            "⠀"
        ),
        color=0x5865F2,
    )
    if not products:
        embed.description = (
            "> ⚠️ No products available yet.\n"
            "> An admin must add products first."
        )
    else:
        for p in products:
            emoji_str = resolve_product_emoji(p.get("emoji", "")) or p.get("emoji", "📦")
            prices = p.get("prices", {})
            price_parts = []
            if prices.get("1day", 0) > 0:
                price_parts.append(f"📅 `1D` **{format_price(prices['1day'])}**")
            if prices.get("7day", 0) > 0:
                price_parts.append(f"📆 `7D` **{format_price(prices['7day'])}**")
            if prices.get("31day", 0) > 0:
                price_parts.append(f"🗓️ `31D` **{format_price(prices['31day'])}**")
            embed.add_field(
                name=f"{emoji_str}  {p['name']}",
                value="  ·  ".join(price_parts) if price_parts else "*No prices set*",
                inline=False,
            )
    embed.set_footer(text="🔐 Premium Digital Store  •  Select a product from the menu below")
    return embed


def product_embed(product: dict) -> discord.Embed:
    prices = product.get("prices", {})
    emoji_str = resolve_product_emoji(product.get("emoji", "")) or product.get("emoji", "📦")
    title = f"{emoji_str}  {product['name']}"

    rows = []
    if prices.get("1day", 0) > 0:
        rows.append(f"┃  📅  **1 Day**　　→　{format_price(prices['1day'])}")
    if prices.get("7day", 0) > 0:
        rows.append(f"┃  📆  **7 Days**　　→　{format_price(prices['7day'])}")
    if prices.get("31day", 0) > 0:
        rows.append(f"┃  🗓️  **31 Days**　→　{format_price(prices['31day'])}")

    embed = discord.Embed(
        title=title,
        description=product.get("description", "") + "\n⠀",
        color=0x7289DA,
    )
    embed.add_field(
        name="💰  Pricing Tiers",
        value="\n".join(rows) if rows else "*No prices set*",
        inline=False,
    )
    if product.get("image_url"):
        embed.set_thumbnail(url=product["image_url"])
    embed.set_footer(text="⏳ Select a duration below to continue")
    return embed


def confirm_embed(product: dict, duration: str, price: float) -> discord.Embed:
    dur_label = {"1day": "1 Day", "7day": "7 Days", "31day": "31 Days"}.get(duration, duration)
    emoji_str = resolve_product_emoji(product.get("emoji", "")) or product.get("emoji", "📦")
    embed = discord.Embed(
        title="🧾  Order Summary",
        description=(
            "> Please **review your order** carefully before confirming.\n"
            "> Once confirmed, proceed to payment.\n"
            "⠀"
        ),
        color=0xF0B232,
    )
    embed.add_field(name="📦  Product", value=f"{emoji_str} {product['name']}", inline=False)
    embed.add_field(name="⏱️  Duration", value=f"**{dur_label}**", inline=True)
    embed.add_field(name="💰  Total", value=f"**{format_price(price)}**", inline=True)
    embed.add_field(name="⠀", value="⠀", inline=True)
    if product.get("image_url"):
        embed.set_thumbnail(url=product["image_url"])
    embed.set_footer(text="✅ Confirm Order  •  ❌ Cancel anytime")
    return embed


def payment_embed(product: dict, duration: str, price: float) -> discord.Embed:
    dur_label = {"1day": "1 Day", "7day": "7 Days", "31day": "31 Days"}.get(duration, duration)
    emoji_str = resolve_product_emoji(product.get("emoji", "")) or product.get("emoji", "📦")
    embed = discord.Embed(
        title="💳  Choose Payment Method",
        description=(
            f"> {emoji_str} **{product['name']}**  ·  {dur_label}  ·  **{format_price(price)}**\n"
            "> ⠀\n"
            "> Select your preferred payment method below.\n"
            "> After paying, press **I Paid** to notify the admin.\n"
            "⠀"
        ),
        color=0x57F287,
    )
    if get_upi_qr_url():
        embed.add_field(name="📲  UPI / QR Pay", value="Scan the QR code to pay instantly", inline=True)
    if get_binance():
        embed.add_field(name="🔶  Binance Pay", value=f"Pay ID: `{get_binance()}`", inline=True)
    embed.set_footer(text="🔒 Secure  •  All payments verified by admin before delivery")
    return embed


def payment_details_upi(product: dict, duration: str, price: float, order_id: str) -> discord.Embed:
    dur_label = {"1day": "1 Day", "7day": "7 Days", "31day": "31 Days"}.get(duration, duration)
    emoji_str = resolve_product_emoji(product.get("emoji", "")) or product.get("emoji", "📦")
    embed = discord.Embed(
        title="📲  UPI / QR Payment",
        description=(
            f"> Scan the **QR code** below and send exactly **{format_price(price)}**.\n"
            f"> After paying, press **✅ I Paid** to notify the admin.\n"
            "> ⚠️ *Do NOT close this message before pressing I Paid!*\n"
            "⠀"
        ),
        color=0x00C853,
    )
    embed.add_field(name="📦  Product", value=f"{emoji_str} {product['name']}", inline=True)
    embed.add_field(name="⏱️  Duration", value=f"**{dur_label}**", inline=True)
    embed.add_field(name="💰  Amount to Send", value=f"**{format_price(price)}**", inline=True)
    embed.set_footer(text=f"🆔 Order: {order_id}  •  🔒 Do not share this ID")
    return embed


def payment_details_binance(product: dict, duration: str, price: float, order_id: str) -> discord.Embed:
    dur_label = {"1day": "1 Day", "7day": "7 Days", "31day": "31 Days"}.get(duration, duration)
    emoji_str = resolve_product_emoji(product.get("emoji", "")) or product.get("emoji", "📦")
    embed = discord.Embed(
        title="🔶  Binance Pay Payment",
        description=(
            f"> Send exactly **{format_price(price)}** to the Binance Pay ID below.\n"
            f"> After paying, press **✅ I Paid** to notify the admin.\n"
            "> ⚠️ *Ensure the amount is exact — wrong amounts cause delays!*\n"
            "⠀"
        ),
        color=0xF0B232,
    )
    embed.add_field(name="🆔  Binance Pay ID", value=f"```{get_binance() or 'Not configured'}```", inline=False)
    embed.add_field(name="📦  Product", value=f"{emoji_str} {product['name']}", inline=True)
    embed.add_field(name="⏱️  Duration", value=f"**{dur_label}**", inline=True)
    embed.add_field(name="💰  Send Exactly", value=f"**{format_price(price)}**", inline=True)
    embed.set_footer(text=f"🆔 Order: {order_id}  •  🔒 Do not share this ID")
    return embed


def admin_approval_embed(order: dict, user: discord.User) -> discord.Embed:
    method_label = "📲  UPI / QR" if order["payment_method"] == "upi" else "🔶  Binance Pay"
    embed = discord.Embed(
        title="🔔  PAYMENT PENDING REVIEW",
        description=(
            f"> 👤 **{user.name}** (`{user.id}`) claims to have paid.\n"
            "> Please **verify the payment** and approve or reject below.\n"
            "⠀"
        ),
        color=0xFEE75C,
    )
    embed.add_field(name="📦  Product", value=order["product_name"], inline=True)
    embed.add_field(name="⏱️  Duration", value=order["duration"], inline=True)
    embed.add_field(name="💰  Amount", value=format_price(order["price"]), inline=True)
    embed.add_field(name="💳  Method", value=method_label, inline=True)
    embed.add_field(name="🆔  Order ID", value=f"`{order['order_id']}`", inline=True)
    embed.add_field(name="⠀", value="⠀", inline=True)
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text="✅ Approve → deliver key   |   ❌ Reject → deny order")
    return embed


# ─────────────────────────────────────────────
#  VIEWS
# ─────────────────────────────────────────────

class StoreView(View):
    def __init__(self):
        super().__init__(timeout=None)
        products = get_all_products()
        if products:
            options = [
                discord.SelectOption(
                    label=p["name"][:100],
                    value=p["id"],
                    description="View details & buy",
                )
                for p in products[:25]
            ]
            select = Select(
                placeholder="🛒 Select a product...",
                options=options,
                custom_id="store_product_select",
            )
            select.callback = self.product_selected
            self.add_item(select)

    async def product_selected(self, interaction: discord.Interaction):
        product_id = interaction.data["values"][0]
        product = find_product(product_id)
        if not product:
            await interaction.response.send_message("❌ Product not found.", ephemeral=True)
            return
        await interaction.response.send_message(
            embed=product_embed(product), view=DurationView(product), ephemeral=True
        )


class BuyNowView(View):
    """Attached to publicly posted product embeds. Starts purchase flow privately."""
    def __init__(self, product: dict):
        super().__init__(timeout=None)
        self.product = product

    @discord.ui.button(label="🛒 Buy Now", style=discord.ButtonStyle.success)
    async def buy_now(self, interaction: discord.Interaction, button: Button):
        product = find_product(self.product["id"])
        if not product:
            await interaction.response.send_message("❌ Product not found.", ephemeral=True)
            return
        await interaction.response.send_message(
            embed=product_embed(product), view=DurationView(product), ephemeral=True
        )


class DurationView(View):
    def __init__(self, product: dict):
        super().__init__(timeout=120)
        self.product = product
        prices = product.get("prices", {})
        options = []
        if prices.get("1day", 0) > 0:
            options.append(discord.SelectOption(label="1 Day", value="1day", description=format_price(prices["1day"]), emoji="📅"))
        if prices.get("7day", 0) > 0:
            options.append(discord.SelectOption(label="7 Days", value="7day", description=format_price(prices["7day"]), emoji="📆"))
        if prices.get("31day", 0) > 0:
            options.append(discord.SelectOption(label="31 Days", value="31day", description=format_price(prices["31day"]), emoji="🗓️"))
        if options:
            select = Select(placeholder="⏳ Choose duration...", options=options)
            select.callback = self.duration_selected
            self.add_item(select)

    async def duration_selected(self, interaction: discord.Interaction):
        duration = interaction.data["values"][0]
        price = self.product["prices"].get(duration, 0)
        view = ConfirmView(self.product, duration, price)
        await _respond(interaction, embed=confirm_embed(self.product, duration, price), view=view)


class ConfirmView(View):
    def __init__(self, product: dict, duration: str, price: float):
        super().__init__(timeout=120)
        self.product = product
        self.duration = duration
        self.price = price

    @discord.ui.button(label="✅ Confirm Order", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        view = PaymentMethodView(self.product, self.duration, self.price)
        await _respond(interaction, embed=payment_embed(self.product, self.duration, self.price), view=view)

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(
            title="❌  Order Cancelled",
            description=(
                "> Your order has been **cancelled**.\n"
                "> No payment was taken. Come back anytime!\n"
                "⠀"
            ),
            color=0xED4245,
        )
        embed.set_footer(text="Browse the store again anytime  •  We'll be here!")
        await _respond(interaction, embed=embed, view=None)


class PaymentMethodView(View):
    def __init__(self, product: dict, duration: str, price: float):
        super().__init__(timeout=180)
        self.product = product
        self.duration = duration
        self.price = price

    @discord.ui.button(label="📲 UPI / QR Pay", style=discord.ButtonStyle.success)
    async def pay_upi(self, interaction: discord.Interaction, button: Button):
        if not get_upi_qr_url():
            await interaction.response.send_message("❌ UPI QR is not configured yet. Contact an admin.", ephemeral=True)
            return
        order_id = create_order(
            interaction.user.id, str(interaction.user),
            self.product, self.duration, self.price, "upi"
        )
        embed = payment_details_upi(self.product, self.duration, self.price, order_id)
        view = IPaidView(order_id, interaction.user)
        custom_qr = get_upi_qr_url()
        if custom_qr:
            # Admin uploaded a custom QR image — use it directly
            embed.set_image(url=custom_qr)
            await _respond(interaction, embed=embed, view=view)
        else:
            # Auto-generate QR from UPI URI
            upi_uri = f"upi://pay?pa={get_upi()}&pn=Store&am={self.price:.2f}&cu=INR&tn=Order{order_id}"
            buf = io.BytesIO()
            segno.make(upi_uri, error="M").save(buf, kind="png", scale=8, border=3)
            buf.seek(0)
            qr_file = discord.File(buf, filename="upi_qr.png")
            embed.set_image(url="attachment://upi_qr.png")
            await _respond(interaction, embed=embed, view=view, attachments=[qr_file])

    @discord.ui.button(label="🔶 Binance Pay", style=discord.ButtonStyle.primary)
    async def pay_binance(self, interaction: discord.Interaction, button: Button):
        if not get_binance():
            await interaction.response.send_message("❌ Binance Pay is not configured yet.", ephemeral=True)
            return
        order_id = create_order(
            interaction.user.id, str(interaction.user),
            self.product, self.duration, self.price, "binance"
        )
        view = IPaidView(order_id, interaction.user)
        await _respond(
            interaction,
            embed=payment_details_binance(self.product, self.duration, self.price, order_id),
            view=view,
        )

    @discord.ui.button(label="↩ Back", style=discord.ButtonStyle.secondary)
    async def go_back(self, interaction: discord.Interaction, button: Button):
        view = ConfirmView(self.product, self.duration, self.price)
        await _respond(interaction, embed=confirm_embed(self.product, self.duration, self.price), view=view)


class IPaidView(View):
    def __init__(self, order_id: str, user: discord.User):
        super().__init__(timeout=None)
        self.order_id = order_id
        self.user = user

    @discord.ui.button(label="I Paid", style=discord.ButtonStyle.success, emoji="<a:confirmar:1466466203341029396>")
    async def i_paid(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ This is not your order.", ephemeral=True)
            return
        order = get_order(self.order_id)
        if not order:
            await interaction.response.send_message("❌ Order not found.", ephemeral=True)
            return
        if order["status"] != "pending":
            await interaction.response.send_message(
                f"⚠️ This order is already **{order['status']}**.", ephemeral=True
            )
            return

        admin_ids = get_admin_ids()
        if not admin_ids:
            await interaction.response.send_message(
                "⚠️ No admin configured. Please contact support.", ephemeral=True
            )
            return

        notified = False
        for admin_id in admin_ids:
            try:
                admin_user = await bot.fetch_user(admin_id)
                view = AdminApproveView(self.order_id, interaction.user)
                await admin_user.send(
                    embed=admin_approval_embed(order, interaction.user),
                    view=view,
                )
                notified = True
            except Exception:
                pass

        if notified:
            embed = discord.Embed(
                title="⏳  Payment Under Review",
                description=(
                    "> ✅ Your payment notification has been **sent to the admin**.\n"
                    "> 🔍 The admin will verify your payment and approve shortly.\n"
                    "> 📬 You will receive a **DM** once your order is processed.\n"
                    "⠀"
                ),
                color=0xFEE75C,
            )
            embed.add_field(name="🆔  Order ID", value=f"`{self.order_id}`", inline=True)
            embed.add_field(name="⏱️  Estimated Time", value="A few minutes", inline=True)
            embed.set_footer(text="🔒 Keep this order ID safe  •  Contact support if delayed")
        else:
            embed = discord.Embed(
                title="⚠️  Admin Notification Failed",
                description=(
                    "> Payment registered but we could not reach the admin.\n"
                    "> Please **contact support** with your Order ID below.\n"
                    "⠀"
                ),
                color=0xED4245,
            )
            embed.add_field(name="🆔  Order ID", value=f"`{self.order_id}`", inline=True)
        await _respond(interaction, embed=embed, view=None)


class AdminApproveView(View):
    def __init__(self, order_id: str, buyer: discord.User):
        super().__init__(timeout=None)
        self.order_id = order_id
        self.buyer = buyer

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, emoji="<:T_:1405541369128157346>")
    async def approve(self, interaction: discord.Interaction, button: Button):
        if not is_admin(interaction.user.id):
            await interaction.response.send_message("❌ You are not an admin.", ephemeral=True)
            return
        order = approve_order(self.order_id)
        if not order:
            await interaction.response.send_message("❌ Order not found.", ephemeral=True)
            return
        key = pop_key(order["product_id"])
        try:
            if key:
                user_embed = discord.Embed(
                    title="🎉  Order Approved!",
                    description=(
                        "> Your payment has been verified and your order is confirmed!\n"
                        "> Copy the key below and enjoy your purchase.\n"
                        "⠀"
                    ),
                    color=0x57F287,
                )
                user_embed.add_field(name="📦  Product", value=order["product_name"], inline=True)
                user_embed.add_field(name="⏱️  Duration", value=order["duration"], inline=True)
                user_embed.add_field(name="⠀", value="⠀", inline=True)
                user_embed.add_field(name="🔑  Your Key", value=f"```{key}```", inline=False)
                user_embed.set_footer(text="🙏 Thank you for your purchase!  •  Enjoy your product!")
            else:
                user_embed = discord.Embed(
                    title="✅  Order Approved — Key Pending",
                    description=(
                        "> Your payment has been verified!\n"
                        "> ⚠️ No key is in stock right now — the admin will **DM you the key manually**.\n"
                        "⠀"
                    ),
                    color=0x57F287,
                )
                user_embed.add_field(name="📦  Product", value=order["product_name"], inline=True)
                user_embed.add_field(name="⏱️  Duration", value=order["duration"], inline=True)
                user_embed.add_field(name="🆔  Order ID", value=f"`{self.order_id}`", inline=False)
                user_embed.set_footer(text="Contact support if you don't receive your key within 1 hour")
            await self.buyer.send(embed=user_embed)
        except Exception:
            pass

        admin_confirm = discord.Embed(
            title="✅  Order Approved",
            description=(
                f"> Order approved for **{self.buyer.name}**.\n"
                + (f"> 🔑 Key delivered: `{key}`" if key else "> ⚠️ No key in stock — deliver manually.")
            ),
            color=0x57F287,
        )
        admin_confirm.add_field(name="🆔  Order ID", value=f"`{self.order_id}`", inline=True)
        await interaction.response.edit_message(embed=admin_confirm, view=None)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, emoji="<:False:1405541343953944606>")
    async def reject(self, interaction: discord.Interaction, button: Button):
        if not is_admin(interaction.user.id):
            await interaction.response.send_message("❌ You are not an admin.", ephemeral=True)
            return
        order = reject_order(self.order_id)
        if not order:
            await interaction.response.send_message("❌ Order not found.", ephemeral=True)
            return
        try:
            user_embed = discord.Embed(
                title="❌  Order Rejected",
                description=(
                    "> Your payment could **not be verified** and your order has been rejected.\n"
                    "> If you believe this is a mistake, please **contact support**.\n"
                    "⠀"
                ),
                color=0xED4245,
            )
            user_embed.add_field(name="🆔  Order ID", value=f"`{self.order_id}`", inline=True)
            user_embed.set_footer(text="Contact support with your Order ID to appeal")
            await self.buyer.send(embed=user_embed)
        except Exception:
            pass
        reject_embed = discord.Embed(
            title="❌  Order Rejected",
            description=f"> Order rejected for **{self.buyer.name}**.",
            color=0xED4245,
        )
        reject_embed.add_field(name="🆔  Order ID", value=f"`{self.order_id}`", inline=True)
        await interaction.response.edit_message(embed=reject_embed, view=None)


# ─────────────────────────────────────────────
#  MODALS
# ─────────────────────────────────────────────

class AddProductModal(Modal, title="➕ Add New Product"):
    name = TextInput(label="Product Name", placeholder="e.g. FFH4X iOS", max_length=100)
    emoji = TextInput(
        label="Custom Emoji (paste full tag: <:name:id>)",
        placeholder="e.g. <:fire:123456789> or <a:glow:987654321>",
        required=False,
        max_length=100,
    )
    image_url = TextInput(label="Image URL", placeholder="https://...", required=False, max_length=500)
    description = TextInput(label="Description", style=discord.TextStyle.paragraph, max_length=1000)
    prices = TextInput(
        label="Prices (1day, 7day, 31day — use 0 to skip)",
        placeholder="e.g. 5.00, 15.00, 25.00",
        max_length=50,
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            raw = [x.strip() for x in self.prices.value.split(",")]
            p1  = float(raw[0]) if len(raw) > 0 and raw[0] else 0
            p7  = float(raw[1]) if len(raw) > 1 and raw[1] else 0
            p31 = float(raw[2]) if len(raw) > 2 and raw[2] else 0
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid price format. Use: `5.00, 15.00, 25.00`", ephemeral=True
            )
            return

        product = add_product(
            name=self.name.value,
            description=self.description.value,
            image_url=self.image_url.value or "",
            emoji=(self.emoji.value or "").strip(),
            price_1d=p1, price_7d=p7, price_31d=p31,
        )
        embed = discord.Embed(
            title="✅ Product Added",
            description=f"**{product['name']}** added.\nID: `{product['id']}`",
            color=0x57F287,
        )
        embed.add_field(name="1 Day",   value=format_price(p1)  if p1  > 0 else "—", inline=True)
        embed.add_field(name="7 Days",  value=format_price(p7)  if p7  > 0 else "—", inline=True)
        embed.add_field(name="31 Days", value=format_price(p31) if p31 > 0 else "—", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class EditPricesModal(Modal, title="✏️ Edit Product Prices"):
    product_id = TextInput(label="Product ID", placeholder="e.g. a1b2c3d4")
    prices = TextInput(
        label="New Prices (1day, 7day, 31day — use 0 to skip)",
        placeholder="e.g. 5.00, 15.00, 25.00",
    )

    async def on_submit(self, interaction: discord.Interaction):
        product = find_product(self.product_id.value.strip())
        if not product:
            await interaction.response.send_message("❌ Product not found.", ephemeral=True)
            return
        try:
            raw = [x.strip() for x in self.prices.value.split(",")]
            p1  = float(raw[0]) if len(raw) > 0 and raw[0] else None
            p7  = float(raw[1]) if len(raw) > 1 and raw[1] else None
            p31 = float(raw[2]) if len(raw) > 2 and raw[2] else None
        except ValueError:
            await interaction.response.send_message("❌ Invalid price format.", ephemeral=True)
            return
        update_product_prices(self.product_id.value.strip(), p1, p7, p31)
        await interaction.response.send_message(
            f"✅ Prices updated for **{product['name']}**.", ephemeral=True
        )


class AddKeyModal(Modal, title="🔑 Add Single Key"):
    product_id = TextInput(label="Product ID", placeholder="e.g. ff-4x-i")
    key_value  = TextInput(label="Key", placeholder="e.g. XXXX-XXXX-XXXX")

    async def on_submit(self, interaction: discord.Interaction):
        product = find_product(self.product_id.value.strip())
        if not product:
            await interaction.response.send_message("❌ Product not found.", ephemeral=True)
            return
        add_key(self.product_id.value.strip(), self.key_value.value.strip())
        count = count_keys(self.product_id.value.strip())
        await interaction.response.send_message(
            f"✅ Key added for **{product['name']}**. Total keys: **{count}**", ephemeral=True
        )


class BulkAddKeyModal(Modal, title="📋 Bulk Add Keys"):
    product_id = TextInput(label="Product ID", placeholder="e.g. ff-4x-i", max_length=50)
    keys_text  = TextInput(
        label="Keys (one per line)",
        style=discord.TextStyle.paragraph,
        placeholder="XXXX-XXXX-XXXX\nYYYY-YYYY-YYYY\nZZZZ-ZZZZ-ZZZZ",
        max_length=4000,
    )

    async def on_submit(self, interaction: discord.Interaction):
        product = find_product(self.product_id.value.strip())
        if not product:
            await interaction.response.send_message("❌ Product not found.", ephemeral=True)
            return
        pid = self.product_id.value.strip()
        raw_lines = self.keys_text.value.splitlines()
        added, skipped = 0, 0
        for line in raw_lines:
            key = line.strip()
            if not key:
                continue
            existing = get_keys(pid)
            if key in existing:
                skipped += 1
            else:
                add_key(pid, key)
                added += 1
        total = count_keys(pid)
        embed = discord.Embed(
            title="📋  Bulk Keys Added",
            color=0x57F287,
        )
        embed.add_field(name="📦  Product", value=product["name"], inline=True)
        embed.add_field(name="✅  Added", value=f"**{added}** keys", inline=True)
        embed.add_field(name="⏭️  Skipped", value=f"**{skipped}** duplicates", inline=True)
        embed.add_field(name="🗃️  Total in Stock", value=f"**{total}** keys", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class SetProductImageModal(Modal, title="🖼️ Set Product Image"):
    product_id = TextInput(label="Product ID", placeholder="e.g. ff-4x-i", max_length=50)
    image_url  = TextInput(
        label="Image URL",
        placeholder="https://i.imgur.com/example.png",
        max_length=500,
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):
        product = find_product(self.product_id.value.strip())
        if not product:
            await interaction.response.send_message("❌ Product not found.", ephemeral=True)
            return
        url = self.image_url.value.strip()
        set_product_image(self.product_id.value.strip(), url)
        if url:
            embed = discord.Embed(
                title="✅  Product Image Set",
                description=f"Image updated for **{product['name']}**.",
                color=0x57F287,
            )
            embed.set_image(url=url)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                f"✅ Image cleared for **{product['name']}**.", ephemeral=True
            )


class RemoveKeyModal(Modal, title="🗑️ Remove Key"):
    product_id = TextInput(label="Product ID", placeholder="e.g. a1b2c3d4")
    key_value  = TextInput(label="Key to Remove", placeholder="e.g. XXXX-XXXX-XXXX")

    async def on_submit(self, interaction: discord.Interaction):
        product = find_product(self.product_id.value.strip())
        if not product:
            await interaction.response.send_message("❌ Product not found.", ephemeral=True)
            return
        removed = remove_key(self.product_id.value.strip(), self.key_value.value.strip())
        if removed:
            await interaction.response.send_message(
                f"✅ Key removed from **{product['name']}**.", ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ Key not found.", ephemeral=True)


class RemoveProductModal(Modal, title="🗑️ Remove Product"):
    product_id = TextInput(label="Product ID (from /admin → List Products)", placeholder="e.g. a1b2c3d4")

    async def on_submit(self, interaction: discord.Interaction):
        product = find_product(self.product_id.value.strip())
        if not product:
            await interaction.response.send_message(
                "❌ Product not found. Use 'List Products' to see IDs.", ephemeral=True
            )
            return
        name = product["name"]
        remove_product(self.product_id.value.strip())
        await interaction.response.send_message(
            f"✅ **{name}** has been removed from the store.", ephemeral=True
        )


class SetBinanceModal(Modal, title="🔶 Set Binance Pay ID"):
    binance_id = TextInput(label="Binance Pay ID", placeholder="e.g. 123456789")

    async def on_submit(self, interaction: discord.Interaction):
        set_binance(self.binance_id.value.strip())
        await interaction.response.send_message(
            f"✅ Binance Pay ID set to `{self.binance_id.value.strip()}`.", ephemeral=True
        )


class SetUPIQRModal(Modal, title="🖼️ Set UPI QR Image URL"):
    qr_url = TextInput(
        label="UPI QR Image URL",
        placeholder="https://i.imgur.com/yourqr.png",
        max_length=500,
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):
        url = self.qr_url.value.strip()
        set_upi_qr_url(url)
        if url:
            embed = discord.Embed(
                title="✅ UPI QR Image Set",
                description="This QR image will now be shown to buyers instead of the auto-generated one.",
                color=0x57F287,
            )
            embed.set_image(url=url)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                "✅ UPI QR image cleared. Auto-generated QR will be used.", ephemeral=True
            )


class AddAdminModal(Modal, title="👮 Add Admin"):
    user_id = TextInput(
        label="Discord User ID",
        placeholder="e.g. 123456789012345678",
        max_length=25,
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            uid = int(self.user_id.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ Invalid user ID. Must be a number.", ephemeral=True)
            return
        if uid in get_admin_ids():
            await interaction.response.send_message(f"⚠️ User `{uid}` is already an admin.", ephemeral=True)
            return
        add_admin(uid)
        try:
            user = await bot.fetch_user(uid)
            name = f"**{user.name}** (`{uid}`)"
        except Exception:
            name = f"`{uid}`"
        await interaction.response.send_message(f"✅ {name} has been added as admin.", ephemeral=True)


# ─────────────────────────────────────────────
#  ADMIN PANEL VIEW
# ─────────────────────────────────────────────

class AdminPanelView(View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(label="🖼️ Set UPI QR", style=discord.ButtonStyle.success, row=0)
    async def set_upi_qr_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(SetUPIQRModal())

    @discord.ui.button(label="🔶 Set Binance Pay", style=discord.ButtonStyle.primary, row=0)
    async def set_binance_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(SetBinanceModal())

    @discord.ui.button(label="➕ Add Product", style=discord.ButtonStyle.success, row=1)
    async def add_product_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(AddProductModal())

    @discord.ui.button(label="✏️ Edit Prices", style=discord.ButtonStyle.primary, row=1)
    async def edit_prices_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(EditPricesModal())

    @discord.ui.button(label="🖼️ Set Image", style=discord.ButtonStyle.primary, row=1)
    async def set_image_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(SetProductImageModal())

    @discord.ui.button(label="🗑️ Remove Product", style=discord.ButtonStyle.danger, row=1)
    async def remove_product_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(RemoveProductModal())

    @discord.ui.button(label="🔑 Add Key", style=discord.ButtonStyle.secondary, row=2)
    async def add_key_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(AddKeyModal())

    @discord.ui.button(label="📋 Bulk Keys", style=discord.ButtonStyle.success, row=2)
    async def bulk_key_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(BulkAddKeyModal())

    @discord.ui.button(label="🗑️ Remove Key", style=discord.ButtonStyle.danger, row=2)
    async def remove_key_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(RemoveKeyModal())

    @discord.ui.button(label="👮 Add Admin", style=discord.ButtonStyle.primary, row=2)
    async def add_admin_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(AddAdminModal())

    @discord.ui.button(label="📋 List Products", style=discord.ButtonStyle.secondary, row=3)
    async def list_products_btn(self, interaction: discord.Interaction, button: Button):
        products = get_all_products()
        if not products:
            await interaction.response.send_message("No products in store yet.", ephemeral=True)
            return
        lines = []
        for p in products:
            k = count_keys(p["id"])
            emoji = resolve_product_emoji(p.get("emoji", ""))
            prefix = (emoji + " ") if emoji else ""
            lines.append(f"**{prefix}{p['name']}** — ID: `{p['id']}` — Keys: **{k}**")
        embed = discord.Embed(title="📋 Product List", description="\n".join(lines), color=0x5865F2)
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ─────────────────────────────────────────────
#  SLASH COMMANDS
# ─────────────────────────────────────────────

@bot.tree.command(name="setup", description="[OWNER ONLY] First-time setup — registers all owners as admins")
async def setup_admin(interaction: discord.Interaction):
    if interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message("❌ Only the bot owner can run this command.", ephemeral=True)
        return
    if get_admin_ids():
        await interaction.response.send_message(
            "✅ Admins already configured. Use `/admin` to manage the store.", ephemeral=True
        )
        return
    for uid in OWNER_IDS:
        add_admin(uid)
    await interaction.response.send_message(
        f"✅ Setup complete! **{len(OWNER_IDS)}** owner(s) registered as admin.\nUse `/admin` to manage the store.",
        ephemeral=True,
    )


@bot.tree.command(name="addadmin", description="[OWNER ONLY] Add a new admin by user ID")
@app_commands.describe(user_id="The Discord user ID to make admin")
async def add_admin_cmd(interaction: discord.Interaction, user_id: str):
    if interaction.user.id not in OWNER_IDS and not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ You don't have permission to do this.", ephemeral=True)
        return
    try:
        uid = int(user_id.strip())
    except ValueError:
        await interaction.response.send_message("❌ Invalid user ID. Must be a number.", ephemeral=True)
        return
    if uid in get_admin_ids():
        await interaction.response.send_message(f"⚠️ User `{uid}` is already an admin.", ephemeral=True)
        return
    add_admin(uid)
    try:
        user = await bot.fetch_user(uid)
        name = f"{user.name} (`{uid}`)"
    except Exception:
        name = f"`{uid}`"
    await interaction.response.send_message(f"✅ {name} has been added as admin.", ephemeral=True)


@bot.tree.command(name="removeadmin", description="[OWNER ONLY] Remove an admin by user ID")
@app_commands.describe(user_id="The Discord user ID to remove from admins")
async def remove_admin_cmd(interaction: discord.Interaction, user_id: str):
    if interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message("❌ Only the bot owner can remove admins.", ephemeral=True)
        return
    try:
        uid = int(user_id.strip())
    except ValueError:
        await interaction.response.send_message("❌ Invalid user ID.", ephemeral=True)
        return
    if uid not in get_admin_ids():
        await interaction.response.send_message(f"⚠️ User `{uid}` is not an admin.", ephemeral=True)
        return
    config["admin_ids"].remove(uid)
    save_config(config)
    await interaction.response.send_message(f"✅ User `{uid}` removed from admins.", ephemeral=True)


@bot.tree.command(name="start", description="[ADMIN] Post the store in this channel")
async def start_store(interaction: discord.Interaction):
    if not check_admin(interaction):
        await interaction.response.send_message("❌ This command is for admins only.", ephemeral=True)
        return
    await interaction.channel.send(embed=store_embed(), view=StoreView())
    await interaction.response.send_message("✅ Store posted!", ephemeral=True)


@bot.tree.command(name="admin", description="[ADMIN] Open the admin control panel")
async def admin_panel(interaction: discord.Interaction):
    if not check_admin(interaction):
        await interaction.response.send_message("❌ This command is for admins only.", ephemeral=True)
        return
    embed = discord.Embed(
        title="⚙️  ADMIN CONTROL PANEL",
        description=(
            "> Manage your store, products, keys and payments below.\n"
            "> Only admins can see this panel.\n"
            "⠀"
        ),
        color=0x5865F2,
    )
    qr_status = "✅ Set" if get_upi_qr_url() else "❌ Not set"
    bin_status = f"`{get_binance()}`" if get_binance() else "❌ Not set"
    embed.add_field(name="📲  UPI QR Image", value=qr_status, inline=True)
    embed.add_field(name="🔶  Binance Pay", value=bin_status, inline=True)
    embed.add_field(name="⠀", value="⠀", inline=True)
    embed.add_field(name="📦  Products", value=f"**{len(get_all_products())}** loaded", inline=True)
    embed.add_field(name="👮  Admins", value=f"**{len(get_admin_ids())}** active", inline=True)
    embed.add_field(name="⠀", value="⠀", inline=True)
    embed.set_footer(text="🔒 Admin only  •  All actions are logged")
    await interaction.response.send_message(embed=embed, view=AdminPanelView(), ephemeral=True)


@bot.tree.command(name="addkey", description="[ADMIN] Add a key for a product")
async def addkey(interaction: discord.Interaction):
    if not check_admin(interaction):
        await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        return
    await interaction.response.send_modal(AddKeyModal())


@bot.tree.command(name="removekey", description="[ADMIN] Remove a key from a product")
async def removekey(interaction: discord.Interaction):
    if not check_admin(interaction):
        await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        return
    await interaction.response.send_modal(RemoveKeyModal())


@bot.tree.command(name="addproduct", description="[ADMIN] Add a new product to the store")
async def addproduct(interaction: discord.Interaction):
    if not check_admin(interaction):
        await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        return
    await interaction.response.send_modal(AddProductModal())


@bot.tree.command(name="addprice", description="[ADMIN] Edit prices for a product")
async def addprice(interaction: discord.Interaction):
    if not check_admin(interaction):
        await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        return
    await interaction.response.send_modal(EditPricesModal())


@bot.tree.command(name="removeproduct", description="[ADMIN] Remove a product from the store")
async def removeproduct(interaction: discord.Interaction):
    if not check_admin(interaction):
        await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        return
    await interaction.response.send_modal(RemoveProductModal())


@bot.tree.command(name="post", description="[ADMIN] Post a specific product in a channel")
@app_commands.describe(channel="The channel to post the product in")
async def post_product(interaction: discord.Interaction, channel: discord.TextChannel):
    if not check_admin(interaction):
        await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        return
    products = get_all_products()
    if not products:
        await interaction.response.send_message("❌ No products yet. Use `/addproduct` first.", ephemeral=True)
        return

    class _PickView(View):
        def __init__(self):
            super().__init__(timeout=60)
            options = [
                discord.SelectOption(label=p["name"][:100], value=p["id"], description="Post this product")
                for p in products[:25]
            ]
            select = Select(placeholder="📦 Choose a product to post...", options=options)
            select.callback = self._chosen
            self.add_item(select)

        async def _chosen(self, intr: discord.Interaction):
            product = find_product(intr.data["values"][0])
            if not product:
                await intr.response.send_message("❌ Product not found.", ephemeral=True)
                return
            await channel.send(embed=product_embed(product), view=BuyNowView(product))
            await intr.response.edit_message(
                content=f"✅ **{product['name']}** posted in {channel.mention}!",
                embed=None, view=None,
            )

    embed = discord.Embed(
        title="📦 Post a Product",
        description=f"Select which product to post in {channel.mention}",
        color=0x5865F2,
    )
    await interaction.response.send_message(embed=embed, view=_PickView(), ephemeral=True)


@bot.tree.command(name="setpayment", description="[ADMIN] Configure UPI QR or Binance Pay")
async def setpayment(interaction: discord.Interaction):
    if not check_admin(interaction):
        await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        return
    view = View(timeout=60)
    qr_btn = Button(label="🖼️ Set UPI QR Image", style=discord.ButtonStyle.success)
    bin_btn = Button(label="🔶 Set Binance Pay", style=discord.ButtonStyle.primary)

    async def qr_cb(i: discord.Interaction):
        await i.response.send_modal(SetUPIQRModal())

    async def bin_cb(i: discord.Interaction):
        await i.response.send_modal(SetBinanceModal())

    qr_btn.callback = qr_cb
    bin_btn.callback = bin_cb
    view.add_item(qr_btn)
    view.add_item(bin_btn)

    embed = discord.Embed(
        title="💳  Configure Payment Methods",
        description=(
            "> **UPI QR** — Paste a URL to your QR code image (e.g. from Imgur)\n"
            "> **Binance Pay** — Enter your Binance Pay numeric ID\n"
            "⠀"
        ),
        color=0x5865F2,
    )
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# ─────────────────────────────────────────────
#  BOT EVENTS
# ─────────────────────────────────────────────

@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user} (ID: {bot.user.id})")
    print(f"📋 Admin IDs: {get_admin_ids()}")
    print(f"🏪 Products: {len(get_all_products())}")
    print(f"🖼️ UPI QR: {'Set' if get_upi_qr_url() else 'Not set'}")
    print(f"🔶 Binance: {get_binance() or 'Not set'}")
    # Show which custom emojis resolved successfully
    resolved = [eid for eid in [_EID_PRODUCT, _EID_DURATION, _EID_AMOUNT, _EID_CONFIRM, _EID_PAYMENT, _EID_PRICE, _EID_PAID] if bot.get_emoji(eid)]
    print(f"🎭 Custom emojis resolved: {len(resolved)}/7")
    if len(resolved) < 7:
        print("  ⚠️  Some emojis not found — bot must be in the server that owns them.")
    print("─" * 40)


bot.run(TOKEN)
