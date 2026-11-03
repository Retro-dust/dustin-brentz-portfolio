import { useCallback, useLayoutEffect, useRef, useState } from "react";
import {
  AnimatePresence,
  motion,
  useReducedMotion,
  useScroll,
  useSpring,
  useTransform,
} from "motion/react";
import About from "./components/About";
import Fx from "./components/Fx";
import Hero from "./components/Hero";
import Inventory from "./components/Inventory";
import QuestLog from "./components/QuestLog";
import { characterLevel, palettes, quests, type PaletteId } from "./data";
import { readPalette, writePalette } from "./palette";
import { scrollToId } from "./scroll";

type Toast = { id: number; amount: number; label: string };

const formatter = new Intl.NumberFormat("en-US");

export default function App() {
  const [palette, setPalette] = useState<PaletteId>(() => readPalette());
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [unlocked, setUnlocked] = useState<string[]>([]);
  const unlockedRef = useRef(new Set<string>());
  const reduce = useReducedMotion();

  const { scrollY, scrollYProgress } = useScroll();
  const ySlow = useTransform(scrollY, [0, 900], [0, 24]);
  const yMid = useTransform(scrollY, [0, 900], [0, 36]);
  const moonY = useTransform(scrollY, [0, 700], [0, 28]);
  const pageBar = useSpring(scrollYProgress, { stiffness: 90, damping: 24, restDelta: 0.001 });
  const heroXpProgress = useTransform(scrollYProgress, [0, 1], [0.68, 1]);
  const barScale = useSpring(heroXpProgress, { stiffness: 90, damping: 24, restDelta: 0.001 });

  useLayoutEffect(() => {
    document.documentElement.dataset.palette = palette;
  }, [palette]);

  const choosePalette = (next: PaletteId) => {
    setPalette(next);
    writePalette(next);
  };

  const onUnlock = useCallback((amount: number, label: string) => {
    if (unlockedRef.current.has(label)) return;
    unlockedRef.current.add(label);
    setUnlocked(Array.from(unlockedRef.current));
    const id = Date.now() + amount;
    setToasts((toastsNow) => [...toastsNow.slice(-2), { id, amount, label }]);
    window.setTimeout(() => {
      setToasts((toastsNow) => toastsNow.filter((toast) => toast.id !== id));
    }, 2200);
  }, []);

  return (
    <div className="lab" data-palette={palette}>
      <a className="skip" href="#inventory">
        Skip to inventory
      </a>
      <Fx palette={palette} ySlow={ySlow} yMid={yMid} />
      <motion.div className="hud-progress" style={{ scaleX: reduce ? 0 : pageBar }} />

      <header className="nav">
        <div className="nav-inner">
          <a className="brand" href="/" aria-label="Back to live homepage">
            <span>DB</span>
            <em className="lab-chip">LAB</em>
          </a>
          <nav className="nav-links" aria-label="Lab">
            <a href="#quest-log" onClick={(event) => scrollToId(event, "quest-log")}>
              Work
            </a>
            <a href="#about" onClick={(event) => scrollToId(event, "about")}>
              About
            </a>
            <a href="/resume.pdf" target="_blank" rel="noopener">
              Résumé
            </a>
            <span className="lv">LV {characterLevel}</span>
          </nav>
          <div className="switcher" role="group" aria-label="Palette">
            {palettes.map((item) => (
              <button
                key={item.id}
                type="button"
                className={palette === item.id ? "active" : ""}
                aria-pressed={palette === item.id}
                onClick={() => choosePalette(item.id)}
              >
                {palette === item.id ? (
                  <motion.span
                    className="nub"
                    layoutId={reduce ? undefined : "palette-nub"}
                    transition={{ type: "spring", bounce: 0.2, visualDuration: 0.35 }}
                  />
                ) : null}
                <span>
                  {item.short} <em>{item.name}</em>
                </span>
              </button>
            ))}
          </div>
        </div>
      </header>

      <main>
        <Hero palette={palette} xpProgress={scrollYProgress} barScale={barScale} moonY={moonY} />
        <Inventory onUnlock={onUnlock} />
        <QuestLog
          onUnlock={onUnlock}
          completed={quests.filter((quest) => unlocked.includes(quest.title)).length}
          xpProgress={scrollYProgress}
        />
        <About onUnlock={onUnlock} />
      </main>

      <footer className="footer">
        <div className="wrap">
          <span>Motion lab · not the live homepage · {palette === "a" ? "Palette A / SNES Night" : "Palette E / Mono Signal"}</span>
          <a href="/">Return to dustinbrentz.com</a>
        </div>
      </footer>

      <div className="xp-pops" aria-live="polite">
        <AnimatePresence>
          {toasts.map((toast) => (
            <motion.div
              key={toast.id}
              className="xp-pop"
              initial={{ opacity: 0, y: 10, scale: 0.92 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -16 }}
              transition={{ type: "spring", bounce: 0.25, visualDuration: 0.35 }}
            >
              +{formatter.format(toast.amount)} XP
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
