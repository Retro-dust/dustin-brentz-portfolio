import { motion, useReducedMotion, type MotionValue } from "motion/react";
import LiveXp from "./LiveXp";
import type { PaletteId } from "../data";
import { characterLevel, heroXpCap } from "../data";
import { scrollToId } from "../scroll";

type Props = {
  palette: PaletteId;
  xpProgress: MotionValue<number>;
  barScale: MotionValue<number>;
  moonY: MotionValue<number>;
};

export default function Hero({ palette, xpProgress, barScale, moonY }: Props) {
  const reduce = useReducedMotion();

  return (
    <section className="hero" id="top">
      {palette === "a" ? (
        <motion.div className="moon" style={{ y: reduce ? 0 : moonY }} aria-hidden="true" />
      ) : null}
      <div className="poster">
        <p className="small-line">Milestone crushing, XP collecting, quest completing,</p>
        <h1>Multi-Class Designer</h1>
        <p className="accent-line">Boss fights optional.</p>
        <div className="cta-row">
          <a className="btn btn-fill" href="#quest-log" onClick={(event) => scrollToId(event, "quest-log")}>
            View case studies
          </a>
          <a className="btn btn-ghost" href="/resume.pdf" target="_blank" rel="noopener">
            Résumé
          </a>
        </div>
        <div className="hero-xp">
          <div className="xp-track" aria-hidden="true">
            <motion.div className="xp-fill" style={{ scaleX: barScale }} />
          </div>
          <div className="xp-meta">
            <span>
              XP <LiveXp progress={xpProgress} /> / {heroXpCap.toLocaleString("en-US")}
            </span>
            <span>LV {characterLevel}</span>
          </div>
        </div>
        <div className="scroll-cue" aria-hidden="true">
          <span>SCROLL</span>
          <i />
        </div>
      </div>
    </section>
  );
}
