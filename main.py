import json
import requests
import discord
import datetime
from discord.ext import commands


class PayPalHandler:
    def __init__(self):
        self.client_data = None
        self.auth = None

    def login(self):
        with open("paypal-info.json") as f:
            self.client_data = json.load(f)
        response = requests.post("https://api-m.sandbox.paypal.com/v1/oauth2/token",
                                 headers={"Accept": "application/json", "Accept-Language": "en-US"},
                                 auth=(self.client_data["client_id"], self.client_data["client_secret"]),
                                 data={"grant_type": "client_credentials"})

        self.auth = response.json()["access_token"]

    def get_next_invoice_number(self):
        response = requests.post("https://api-m.sandbox.paypal.com/v2/invoicing/generate-next-invoice-number",
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.auth}"})
        return response.json()["invoice_number"]

    def create_invoice(self, email, product):
        with open("products.json") as f:
            products = json.load(f)
        product_info = products[product]
        response = requests.post("https://api-m.sandbox.paypal.com/v2/invoicing/invoices",
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.auth}"},
                                 json={
                                     "detail": {
                                         "invoice_number": f"#{self.get_next_invoice_number()}",
                                         "invoice_date": datetime.date.today().strftime("%Y-%m-%d"),
                                         "currency_code": "GBP",
                                         "payment_term": {
                                             "due_date": (
                                                     datetime.date.today() + datetime.timedelta(days=1)).strftime(
                                                 "%Y-%m-%d")
                                         }
                                     },
                                     "invoicer": {
                                         "email_address": self.client_data["email"]
                                     },
                                     "primary_recipients": [{
                                         "billing_info": {"email_address": email}
                                     }],
                                     "items": [
                                         {"name": product_info["name"],
                                          "description": product_info["description"],
                                          "quantity": 1,
                                          "unit_amount": {
                                              "currency_code": "GBP",
                                              "value": product_info["cost"]
                                          },
                                          "unit_of_measure": "QUANTITY"}
                                     ]
                                 })
        payload = response.json()
        invoice_id = payload["href"][::-1][:payload["href"][::-1].index("/")][::-1]
        return response.json(), invoice_id

    def send(self, invoice_id):
        response = requests.post(f"https://api-m.sandbox.paypal.com/v2/invoicing/invoices/{invoice_id}/send",
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.auth}"},
                                 json={"send_to_invoicer": True})
        return response.json()

    def check(self, invoice_id):
        response = requests.get(f"https://api-m.sandbox.paypal.com/v2/invoicing/invoices/{invoice_id}",
                                headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.auth}"})
        return response.json()


# INV2-2PRL-ADU6-FJQW-2KHQ - Paid Invoice For Testing Purposes

class CommandClient(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=".", intents=discord.Intents.all())
        with open("botconfig.json") as f:
            self.config = json.load(f)

    async def on_ready(self):
        print(f"Logged in as {self.user}")


class Main:
    def __init__(self):
        self.discord_client = CommandClient()
        self.paypal_handler = PayPalHandler()

    def register_commands_to_bot(self):
        @self.discord_client.command()
        async def sync(ctx):
            synced = await self.discord_client.tree.sync(guild=discord.Object(self.discord_client.config["guild_id"]))
            await ctx.send(f"Synced {str(len(synced))} commands")

        @self.discord_client.tree.command(name="create", guild=discord.Object(self.discord_client.config["guild_id"]))
        @discord.app_commands.describe(email="PayPal email to send invoice to", product="Product id name")
        async def create(interaction: discord.Interaction, email: str, product: str):
            view = discord.ui.View()
            data = self.paypal_handler.create_invoice(email, product)
            self.paypal_handler.send(data[1])
            invoice_pay_link = self.paypal_handler.check(data[1])['detail']['metadata']['recipient_view_url']
            print(invoice_pay_link)
            embed = discord.Embed(colour=discord.Colour.from_rgb(255, 215, 0), title="PayPal Invoice Generated")
            embed.add_field(name="Information", value=f"""
            Invoiced To: {email}
            Product: {product}
            Due By: 24 Hours""")
            view.add_item(
                discord.ui.Button(label="Open Pay Page", style=discord.ButtonStyle.link, url=invoice_pay_link,
                                  emoji="🔗"))
            await interaction.response.send_message(embed=embed, view=view)

        @self.discord_client.tree.command(name="check", guild=discord.Object(self.discord_client.config["guild_id"]))
        @discord.app_commands.describe(invoice_id="Invoice to check")
        async def check(interaction: discord.Interaction, invoice_id: str):
            invoice_information = self.paypal_handler.check(invoice_id)
            embed = discord.Embed(colour=discord.Colour.from_rgb(255, 215, 0), title=invoice_id)
            embed.add_field(name="Status", value=invoice_information["status"])
            await interaction.response.send_message(embed=embed)

    def run(self):
        self.paypal_handler.login()
        self.discord_client.run(self.discord_client.config["token"])

if __name__ == "__main__":
    application = Main()
    application.register_commands_to_bot()
    application.run()
