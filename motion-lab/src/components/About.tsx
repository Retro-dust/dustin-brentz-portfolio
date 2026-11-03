import { motion, useReducedMotion } from "motion/react";

type Props = {
  onUnlock: (amount: number, label: string) => void;
};

export default function About({ onUnlock }: Props) {
  const reduce = useReducedMotion();

  return (
    <section className="section about" id="about">
      <div className="wrap about-grid">
        <motion.div
          initial={reduce ? false : { opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.4 }}
          onViewportEnter={() => onUnlock(300, "party sheet")}
          transition={{ type: "spring", bounce: 0.12, visualDuration: 0.5 }}
        >
          <p className="kicker">Party / About</p>
          <h2>Designer by class, generalist by choice.</h2>
          <p className="lede">
            15 years across product, systems and AI. I like hard problems, clear teams, and shipping.
          </p>
          <a className="btn btn-fill" href="/">
            More about me
          </a>
        </motion.div>
        <motion.div
          className="portrait hud-corners"
          initial={reduce ? false : { opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.5 }}
          transition={{ type: "spring", bounce: 0.2, visualDuration: 0.55 }}
          aria-hidden="true"
        >
          <span className="c-bl" />
          <span className="c-br" />
          <span>DB · LV 12</span>
        </motion.div>
      </div>
    </section>
  );
}
