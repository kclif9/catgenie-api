"""Example: authenticate and list CatGenie devices."""

import asyncio

from catgenie import CatGenieAuth, CatGenieClient


async def main() -> None:
    """Authenticate using phone number and list devices."""
    country_code = int(input("Country code (e.g. 61): "))
    phone = input("Phone number (without country code): ")

    async with CatGenieAuth() as auth:
        # Mirror app flow: config/v1/url is always called first (preflight)
        await auth.get_base_url(country_code, phone)
        print("config/v1/url: OK")

        result = await auth.request_login_code(country_code, phone)
        print(f"generateLoginCode: status={result['status']}")
        print("(If no SMS arrives within 60s, try again or use the mobile app)")

        code = input("Enter the SMS code: ")
        creds = await auth.login(country_code=country_code, phone=phone, code=code)

    print("\nAuthenticated (refresh token expires ~10 years)")

    async with CatGenieClient(creds) as client:
        devices = await client.get_devices()

    print(f"\nFound {len(devices)} device(s):\n")
    for dev in devices:
        print(f"  - {dev.name}")
        print(f"    Manufacturer ID: {dev.manufacturer_id}")
        print(f"    MAC Address:     {dev.mac_address}")
        print(f"    Firmware:        {dev.fw_version}")
        print(f"    Online:          {dev.is_online}")
        print(f"    Last Clean:      {dev.last_clean}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
