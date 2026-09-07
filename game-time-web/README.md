This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

An ESPN-sourced scoreboard appears above the chat with NFL, college football,
NBA, MLB, and NHL filters. The browser requests `/api/scoreboard?league=nfl`;
the Next.js route fetches ESPN's public scoreboard endpoint with an eight-second
timeout and 60-second caching. No API key is required. The feed may change or
be unavailable; empty and failed responses are handled without blocking chat.
Cards link to ESPN, show live games first, and can be scrolled horizontally.
Automatic updates run every minute while the tab is visible and can be paused.
The displayed games follow ESPN's default current slate (which can span a week
for football), limited to 30 cards. This is a custom scoreboard using ESPN data,
not an official ESPN embed. Feed availability is an external dependency.

The main chat supports English voice dictation through the browser's Web Speech
API when available on HTTPS (or localhost). Click **Speak your message**, allow
microphone access, dictate, then review/edit the text and press **Send**. Speech
is appended to the existing draft; messages are limited to 1,000 characters.
Recognition stops after an utterance or when the user presses Stop. Unsupported
browsers retain typed input. No audio-upload endpoint or recording storage is
added to the app; the browser's speech service may process audio remotely.
Only the reviewed text is sent to the chat API after Send. Real microphone and
permission behavior should be checked on target devices before deployment.

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
