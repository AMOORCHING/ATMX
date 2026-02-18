import type { EventData } from "../types";

export const EVENTS: EventData[] = [
  {
    id: "nyc-summer-sounds",
    name: "Summer Sounds Festival",
    tagline: "Three days of music in Central Park",
    description:
      "Indie rock, hip-hop, and electronic music in the heart of Manhattan. " +
      "50,000+ attendees across three stages with the city skyline as your backdrop.",
    date: "2026-06-14T00:00:00Z",
    dateDisplay: "June 14–16, 2026",
    time: "Gates open 12 PM",
    venue: "Central Park SummerStage",
    city: "New York",
    state: "NY",
    lat: 40.7695,
    lng: -73.971,
    ticketPrice: 125,
    genre: "Indie / Electronic",
    emoji: "🎸",
    gradient: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
  },
  {
    id: "chi-lakefront",
    name: "Lakefront Music Fest",
    tagline: "Chicago's premier outdoor festival",
    description:
      "Top-tier acts against the stunning Lake Michigan skyline. Four stages, " +
      "craft food vendors, and the best of Chicago's music scene.",
    date: "2026-07-18T00:00:00Z",
    dateDisplay: "July 18–19, 2026",
    time: "Gates open 11 AM",
    venue: "Grant Park",
    city: "Chicago",
    state: "IL",
    lat: 41.8758,
    lng: -87.6189,
    ticketPrice: 95,
    genre: "Rock / Hip-Hop",
    emoji: "🎹",
    gradient: "linear-gradient(135deg, #0093E9 0%, #80D0C7 100%)",
  },
  {
    id: "hou-bayou-beats",
    name: "Bayou Beats Festival",
    tagline: "Southern sound on the bayou",
    description:
      "A celebration of Southern hip-hop, R&B, and Cajun-infused music along " +
      "Buffalo Bayou. Food trucks, art installations, and Texas-sized energy.",
    date: "2026-03-28T00:00:00Z",
    dateDisplay: "March 28–29, 2026",
    time: "Gates open 1 PM",
    venue: "Eleanor Tinsley Park",
    city: "Houston",
    state: "TX",
    lat: 29.7636,
    lng: -95.3808,
    ticketPrice: 85,
    genre: "Hip-Hop / R&B",
    emoji: "🎤",
    gradient: "linear-gradient(135deg, #F97316 0%, #EC4899 100%)",
  },
  {
    id: "mia-neon-nights",
    name: "Neon Nights Festival",
    tagline: "Miami's biggest electronic music experience",
    description:
      "World-class DJs take over Bayfront Park with immersive visuals, " +
      "three waterfront stages, and the electric Miami nightlife energy.",
    date: "2026-04-18T00:00:00Z",
    dateDisplay: "April 18–19, 2026",
    time: "Gates open 4 PM",
    venue: "Bayfront Park",
    city: "Miami",
    state: "FL",
    lat: 25.7743,
    lng: -80.1862,
    ticketPrice: 110,
    genre: "Electronic / House",
    emoji: "🎧",
    gradient: "linear-gradient(135deg, #06B6D4 0%, #8B5CF6 100%)",
  },
  {
    id: "nash-honkytonk",
    name: "Honky Tonk Open Air",
    tagline: "Country under the stars",
    description:
      "Country, Americana, and bluegrass on the banks of the Cumberland River. " +
      "Nashville's most authentic outdoor music experience with 30+ artists.",
    date: "2026-06-21T00:00:00Z",
    dateDisplay: "June 21–22, 2026",
    time: "Gates open 2 PM",
    venue: "Riverfront Park",
    city: "Nashville",
    state: "TN",
    lat: 36.1627,
    lng: -86.7748,
    ticketPrice: 75,
    genre: "Country / Americana",
    emoji: "🤠",
    gradient: "linear-gradient(135deg, #F59E0B 0%, #EF4444 100%)",
  },
  {
    id: "sea-emerald",
    name: "Emerald City SoundFest",
    tagline: "Pacific Northwest's favorite festival",
    description:
      "Indie and alternative music at the base of the Space Needle. " +
      "Local craft beer, PNW food scene, and two days of unforgettable performances.",
    date: "2026-07-25T00:00:00Z",
    dateDisplay: "July 25–26, 2026",
    time: "Gates open 12 PM",
    venue: "Seattle Center",
    city: "Seattle",
    state: "WA",
    lat: 47.6205,
    lng: -122.3493,
    ticketPrice: 90,
    genre: "Indie / Alternative",
    emoji: "🌲",
    gradient: "linear-gradient(135deg, #10B981 0%, #3B82F6 100%)",
  },
];

export function getEventById(id: string): EventData | undefined {
  return EVENTS.find((e) => e.id === id);
}
