import { useRef } from "react";
import { motion, useInView, useReducedMotion, type MotionValue } from "motion/react";
import LiveXp from "./LiveXp";
import { quests } from "../data";

type Props = {
  onUnlock: (amount: number, label: string) => void;
  completed: number;
  xpProgress: MotionValue<number>;
};

export default function QuestLog({ onUnlock, completed, xpProgress }: Props) {
  return (
    <section className="section" id="quest-log">
      <div className="wrap">
        <div className="quest-head">
          <div>
            <p className="kicker">Quest log</p>
            <h2>Case studies, earned the hard way.</h2>
          </div>
          <div className="quest-stats">
            QUEST LOG · {completed} / {quests.length}
            <br />
            XP <LiveXp progress={xpProgress} />
          </div>
        </div>
        {quests.map((quest, index) => (
          <QuestBand key={quest.id} quest={quest} index={index} onUnlock={onUnlock} />
        ))}
      </div>
    </section>
  );
}

function QuestBand({
  quest,
  index,
  onUnlock,
}: {
  quest: (typeof quests)[number];
  index: number;
  onUnlock: (amount: number, label: string) => void;
}) {
  const ref = useRef<HTMLElement>(null);
  const inView = useInView(ref, { amount: 0.45, once: true });
  const reduce = useReducedMotion();

  return (
    <motion.article
      ref={ref}
      className={`band hud-corners ${inView ? "active" : ""}`}
      initial={reduce ? false : { opacity: 0, y: 22 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.45 }}
      onViewportEnter={() => onUnlock(quest.xp, quest.title)}
      transition={{ type: "spring", bounce: 0.12, visualDuration: 0.5, delay: index * 0.04 }}
    >
      <span className="c-bl" />
      <span className="c-br" />
      <div className="band-copy">
        <p className="qid">Quest {quest.id}</p>
        <h3>{quest.title}</h3>
        <p>{quest.blurb}</p>
        <div className="band-actions">
          <a className="btn btn-ghost" href={quest.href}>
            Read case study
          </a>
          <span className="xp-badge">+{quest.xp.toLocaleString("en-US")} XP</span>
        </div>
      </div>
      <div className="art" aria-hidden="true">
        {quest.images.slice(0, 3).map((src, i) => (
          <motion.figure
            key={src}
            initial={{ opacity: 0, y: 10 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.4 }}
            transition={{ delay: 0.08 * i, type: "spring", bounce: 0.12, visualDuration: 0.4 }}
          >
            <img src={src} alt="" />
          </motion.figure>
        ))}
      </div>
    </motion.article>
  );
}
