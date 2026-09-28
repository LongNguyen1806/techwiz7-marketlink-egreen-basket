export const DEFAULT_BOOKING_HORIZON_DAYS = 7;

export const LAST_UPDATED = { privacy: '27/09/2026' };

export const CONTACT = {
  address: 'Ben Thanh Ward, District 1, Ho Chi Minh City, Vietnam',
  email: 'support@marketlink.example',
  phone: '+84 28 0000 0000',
  hours: 'Every day, 06:00–18:00 (GMT+7)',
  replyTime: 'We reply to emails within one business day.',
  latitude: 10.7725,
  longitude: 106.698,
};

export const TEAM = [
  {
    name: 'Tang Huynh Tuan Tu',
    role: 'Shopper experience',
    focus: 'Cart, checkout, orders, favourites and the assistant widget.',
  },
  {
    name: 'Long Nguyen',
    role: 'Farmer tools & platform',
    focus: 'Stall dashboard, orders, stock, pickup slots and the backend core.',
  },
  {
    name: 'Minh Anh',
    role: 'Admin console & public pages',
    focus: 'Approvals, moderation, markets, reports and the pages you are reading.',
  },
];

export const howItWorks = (horizonDays = DEFAULT_BOOKING_HORIZON_DAYS) => [
  {
    title: 'Find',
    text: 'Search produce, markets or the stalls you already know, and see what is on sale this week.',
  },
  {
    title: 'Reserve',
    text: `Pick a pickup slot at the stall and reserve up to ${horizonDays} days ahead. The stall confirms your order.`,
  },
  {
    title: 'Pick up at the market',
    text: 'Go to the stall in your slot, check your produce and pay when you collect.',
  },
];

export const VALUES = [
  { title: 'Fresh and local', text: 'Produce comes from farmers who sell at markets near you, not from a warehouse.' },
  { title: 'Fair to farmers', text: 'Stalls know what is reserved before market day, so they pick and bring what is wanted.' },
  { title: 'Checked listings', text: 'Every stall is approved by our team, and every new listing is reviewed before shoppers see it.' },
  { title: 'Pay at the stall', text: 'No card details online. You pay the farmer in person when you collect.' },
];

export const faq = (horizonDays = DEFAULT_BOOKING_HORIZON_DAYS) => [
  {
    id: 'pay',
    question: 'How do I pay?',
    answer: 'You pay at the stall when you collect your order. There is no online payment on MarketLink.',
  },
  {
    id: 'delivery',
    question: 'Do you deliver?',
    answer: 'No. Orders are picked up at the stall, at the market, in the pickup slot you chose.',
  },
  {
    id: 'cutoff',
    question: 'What is the order cut-off?',
    answer:
      'Each stall sets how many hours before a pickup slot it stops taking changes. After the cut-off an order can no longer be changed or cancelled, because the farmer has started preparing it.',
  },
  {
    id: 'family',
    question: 'Can my family share one account?',
    answer:
      'Yes. Sign in on as many phones and computers as you like. Each device keeps its own cart, while orders and favourites are shared across all of them. Signing out on one device does not sign out the others.',
  },
  {
    id: 'ahead',
    question: 'How far ahead can I order?',
    answer: `Up to ${horizonDays} days ahead, for any pickup slot a stall offers in that time.`,
  },
  {
    id: 'change',
    question: 'Can I change or cancel an order?',
    answer:
      'Yes, from My orders, until the stall’s cut-off. Once a stall has accepted your order, a change becomes a request that the stall approves or declines.',
  },
  {
    id: 'missed',
    question: 'What if I cannot make it to the pickup?',
    answer:
      'Cancel before the cut-off so the stall does not prepare it. A pickup that is missed without cancelling counts against your account.',
  },
  {
    id: 'checked',
    question: 'How are stalls and products checked?',
    answer:
      'Every stall is approved by our team before it can sell. Every new or renamed listing is reviewed, with the help of automated checks, before shoppers can see it.',
  },
  {
    id: 'limits',
    question: 'Is there a limit on how much I can order?',
    answer: 'A stall may set a minimum and a maximum quantity per order for each product, based on what it can supply.',
  },
  {
    id: 'sell',
    question: 'How do I sell on MarketLink?',
    answer:
      'Sign up as a seller with your stall details. Once our team approves your stall, you choose your markets and pickup slots and list your produce.',
  },
];

export const PRIVACY_SECTIONS = [
  {
    id: 'who-we-are',
    title: 'Who we are',
    paragraphs: [
      'MarketLink is a pre-order platform for local farmers’ markets, built by the MarketLink team as a TechWiz 7 project. When this policy says “we”, “us” or “our”, it means that team.',
      'This policy explains what personal information we collect when you use MarketLink, why, who can see it, and the choices you have.',
    ],
  },
  {
    id: 'what-we-collect',
    title: 'Information we collect',
    paragraphs: ['Information you give us:'],
    list: [
      'Account details: your name, email address, phone number, address and password. Passwords are stored only in a hashed form that cannot be read back.',
      'Stall details, if you sell: stall name, contact person, phone, address, description, photos, the markets you sell at and your selling days. We look up map coordinates for your address so shoppers can find you.',
      'Orders: the products, quantities, pickup market and slot, notes you add, and any change requests.',
      'Reviews and replies you write, and the stalls, products and markets you save as favourites.',
      'Questions you ask the MarketLink assistant.',
    ],
    after: [
      'Information collected automatically: your IP address and basic request details, used to keep the service secure and to prevent abuse, when you last signed in, and a record of important changes to accounts, orders and listings.',
    ],
  },
  {
    id: 'browser',
    title: 'What is stored in your browser',
    paragraphs: [
      'MarketLink keeps a few things in your browser’s local storage: your sign-in session, your cart (which is why each device has its own cart), announcements you have dismissed and display preferences such as the colour theme.',
      'We do not use advertising or analytics cookies, and we do not use tracking pixels.',
    ],
  },
  {
    id: 'how-we-use',
    title: 'How we use your information',
    list: [
      'To run your orders: pass them to the stall, confirm them, and tell you when they are ready.',
      'To show markets, stalls and produce, and to calculate distances when you share your location in the browser.',
      'To send notifications in the app and emails about important order events.',
      'To keep the marketplace safe: approving stalls, reviewing listings (with the help of automated checks), handling reports and preventing abuse.',
      'To answer your questions through the assistant, which looks up only the information your account is allowed to see.',
      'To understand how the service is used, from overall counts only. We do not build advertising profiles.',
    ],
  },
  {
    id: 'who-can-see',
    title: 'Who can see your information',
    list: [
      'Stalls you order from see your name, phone number and order, so they can prepare it and reach you about pickup.',
      'Shoppers who order from a stall see the stall’s public details and phone number.',
      'Reviews are public and show your display name.',
      'Our administrators can see account and order details when they approve stalls, moderate content or help with a problem.',
      'We never sell your personal information.',
    ],
  },
  {
    id: 'providers',
    title: 'Services we rely on',
    paragraphs: ['A few trusted services process some information for us:'],
    list: [
      'Google Gemini: answers the questions you ask the assistant, and reviews the text and photos of new listings. We use the paid Gemini API, under which Google does not use this content to improve its products. Assistant conversations are not stored on our servers after the answer is sent.',
      'OpenStreetMap: shows maps, and turns stall addresses into map coordinates.',
      'Google Maps: shows the map on our Contact page and opens when you ask for directions.',
      'An email provider: delivers the emails we send about your orders.',
      'Our hosting provider: runs the servers and database where MarketLink’s data is kept.',
    ],
  },
  {
    id: 'retention',
    title: 'How long we keep it',
    list: [
      'Account information is kept while your account is active.',
      'Sign-ups that are never used (no sign-in, no order and nothing saved for three months) may be deleted.',
      'Orders, reviews and the record of important changes are kept so that orders, disputes and moderation decisions can be checked later.',
      'Assistant conversations are kept only in your browser tab and are gone when you reload the page.',
    ],
  },
  {
    id: 'security',
    title: 'How we protect it',
    paragraphs: [
      'Passwords are hashed, sign-in sessions expire and are renewed securely, and each account can only reach the data its role allows. Connections to MarketLink are encrypted when the site is served over HTTPS. No system is perfectly secure, so please use a strong password that you do not use elsewhere.',
    ],
  },
  {
    id: 'your-choices',
    title: 'Your choices',
    list: [
      'You can view and update your profile at any time, and change your password.',
      'You can sign out on any device without affecting your other devices.',
      'You can ask us for a copy of your information, or to delete your account, by contacting us. Some records, such as completed orders, may be kept where we need them for the reasons above.',
    ],
  },
  {
    id: 'children',
    title: 'Children',
    paragraphs: ['MarketLink is not intended for children under 16, and we do not knowingly collect their information.'],
  },
  {
    id: 'changes',
    title: 'Changes to this policy',
    paragraphs: [
      'We may update this policy as MarketLink changes. The date at the top shows the latest version, and we will announce significant changes on the site.',
    ],
  },
  {
    id: 'contact',
    title: 'Contact us',
    paragraphs: [`Questions about this policy or your information: email ${CONTACT.email} or visit our Contact page.`],
  },
];
