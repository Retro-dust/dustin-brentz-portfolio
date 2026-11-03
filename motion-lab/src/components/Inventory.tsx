import { useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { classes } from "../data";

const list = {
  hidden: {},
  show: {
    transition: { staggerChildren: 0.09, delayChildren: 0.05 },
  },
};

const item = {
  hidden: { opacity: 0, y: 18 },
  show: {
    opacity: 1,
    y: 0,
    transition: { type: "spring" as const, bounce: 0.18, visualDuration: 0.45 },
  },
};

type Props = {
  onUnlock: (amount: number, label: string) => void;
};

export default function Inventory({ onUnlock }: Props) {
  const [inspected, setInspected] = useState(0);
  const reduce = useReducedMotion();

  return (
    <section className="section" id="inventory">
      <div className="wrap">
        <div className="inventory-head">
          <p className="kicker">Inventory</p>
          <h2>Six classes, one save file.</h2>
          <p className="lede">Each slot is a craft I have leveled on shipped work. Hover to inspect.</p>
        </div>
        <motion.div
          className="grid-3"
          variants={list}
          initial={reduce ? false : "hidden"}
          whileInView="show"
          viewport={{ once: true, amount: 0.25 }}
          onViewportEnter={() => onUnlock(400, "class inventory")}
        >
          {classes.map((cls, index) => {
            const active = inspected === index;
            return (
              <motion.button
                key={cls.name}
                type="button"
                className={`card hud-corners ${active ? "active" : ""}`}
                variants={item}
                whileHover={reduce ? undefined : { y: -4 }}
                onMouseEnter={() => setInspected(index)}
                onFocus={() => setInspected(index)}
                aria-pressed={active}
              >
                <span className="c-bl" />
                <span className="c-br" />
                <div className="card-top">
                  <h3>{cls.name}</h3>
                  <span className="lv-mini">LV {cls.lv}</span>
                </div>
                <div className="card-bar" aria-hidden="true">
                  <motion.span
                    initial={{ scaleX: 0 }}
                    whileInView={{ scaleX: cls.xp }}
                    viewport={{ once: true, amount: 0.6 }}
                    transition={{ type: "spring", bounce: 0, visualDuration: 0.7, delay: 0.1 * index }}
                    style={{ display: "block" }}
                  />
                </div>
                <div className="tags">
                  {active
                    ? cls.tags.map((tag) => (
                        <span className="tag" key={tag}>
                          {tag}
                        </span>
                      ))
                    : null}
                </div>
              </motion.button>
            );
          })}
        </motion.div>
      </div>
    </section>
  );
}
