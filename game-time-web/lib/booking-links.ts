// Keep aligned with Game-Time/booking_links.py. Unknown destinations fail closed.
const bookingHosts = [
  "ticketmaster.com", "ticketmaster.evyy.net", "stubhub.com", "seatgeek.com",
  "vividseats.com", "axs.com", "booking.com", "hotels.com", "agoda.com",
  "hostelworld.com", "expedia.com", "trip.com", "klook.com", "kkday.com",
  "aviasales.com", "kiwi.com", "airalo.com", "gettransfer.com", "drimsim.com",
  "getrentacar.com", "gocity.com", "ektatraveling.com", "economybookings.com",
  "bikesbooking.com", "qeeq.com", "wegotrip.com", "autoeurope.com",
  "radicalstorage.com", "intui.travel", "saily.com", "tp.st",
];

export function isBookingUrl(value?: string): boolean {
  if (!value) return false;
  try {
    const url = new URL(value);
    const host = url.hostname.toLowerCase().replace(/\.$/, "");
    if (["help", "support", "blog", "news"].includes(host.split(".")[0])) return false;
    if (host === "ticketmaster.evyy.net" && url.searchParams.has("u")) {
      const destination = url.searchParams.get("u")!;
      if (new URL(destination).hostname === host || !isBookingUrl(destination)) return false;
    }
    return url.protocol === "https:" && !url.username && !url.password && !url.port
      && bookingHosts.some(domain => host === domain || host.endsWith(`.${domain}`))
      && !/\/(?:news|blogs?|articles?|schedules?|scores|standings|help|support|about|press|guides?)(?:[/.?\-]|$)/i.test(decodeURIComponent(url.pathname));
  } catch {
    return false;
  }
}
