export type PaletteId = "a" | "e";

export const palettes: { id: PaletteId; name: string; short: string }[] = [
  { id: "a", name: "SNES Night", short: "A" },
  { id: "e", name: "Mono Signal", short: "E" },
];

export const classes = [
  {
    name: "Product Design",
    lv: 24,
    xp: 0.86,
    tags: ["Systems", "Product Design", "AI-assisted workflows", "Design ops"],
  },
  {
    name: "Design Systems",
    lv: 12,
    xp: 0.62,
    tags: ["Tokens", "Foundations", "Theming"],
  },
  {
    name: "Prototyping",
    lv: 18,
    xp: 0.74,
    tags: ["Figma", "Motion", "HTML / CSS"],
  },
  {
    name: "Research",
    lv: 11,
    xp: 0.48,
    tags: ["Interviews", "Usability", "Synthesis"],
  },
  {
    name: "Front-end",
    lv: 14,
    xp: 0.57,
    tags: ["Design-dev", "Accessibility", "CSS"],
  },
  {
    name: "AI UX",
    lv: 9,
    xp: 0.41,
    tags: ["Copilots", "Prompt UX", "0 → 1"],
  },
] as const;

export const quests = [
  {
    id: "001",
    title: "Whiteboard AI",
    blurb: "Turning a blank canvas into a collaborator. 0 → 1 AI features shipped to millions.",
    xp: 1200,
    href: "/brightidea-whiteboard-case-study",
    images: [
      "/assets/work/7ff540f6279d4f63b35748fead2af460.png",
      "/assets/work/02b819fff4fc4d3c925b71530fd71dc8.png",
      "/assets/work/9d0a91f7ba684c5bbd6ad01769f81806.png",
      "/assets/hero-case-whiteboard.png",
    ],
  },
  {
    id: "002",
    title: "Marketo Editors",
    blurb: "Rebuilt Adobe legacy editors into the systems marketers actually enjoy.",
    xp: 1800,
    href: "/marketo-editors-case-study",
    images: [
      "/assets/work/7116b695832d4162a077bb6d1d0126d0.png",
      "/assets/hero-case-marketo.png",
      "/assets/work/59bcf173731045f3a2b17a5b7cfa106b.png",
    ],
  },
  {
    id: "003",
    title: "Fusion NRE / NCE",
    blurb: "Field-ready time and safety tools across a complex enterprise stack.",
    xp: 1500,
    href: "/product-design",
    images: [
      "/assets/work/cb1f19105d6c4b91b731f1d8ae883562.png",
      "/assets/work/12d5513b79b04d8a807394fb1179b876.jpg",
      "/assets/work/d22be3920aa444a18337ea39ac9b0410.png",
    ],
  },
] as const;

export const heroXpCap = 10000;
export const heroXpSaved = 6800;
export const characterLevel = 12;
