import { useMemo } from "react";
import { motion, useReducedMotion, type MotionValue } from "motion/react";
import type { PaletteId } from "../data";

type Props = {
  palette: PaletteId;
  ySlow: MotionValue<number>;
  yMid: MotionValue<number>;
};

function makeStars(count: number) {
  const stars = [];
  for (let i = 0; i < count; i += 1) {
    const seed = (i * 9973) % 1000;
    stars.push({
      id: i,
      left: `${(seed * 17) % 100}%`,
      top: `${(seed * 29) % 100}%`,
      delay: `${(i % 12) * 0.35}s`,
      kind: i % 11 === 0 ? "gold" : i % 3 === 0 ? "dim" : "plain",
    });
  }
  return stars;
}

export default function Fx({ palette, ySlow, yMid }: Props) {
  const reduce = useReducedMotion();
  const stars = useMemo(() => makeStars(56), []);

  return (
    <div className="fx" aria-hidden="true">
      {palette === "a" ? (
        <motion.div className="stars" style={{ y: reduce ? 0 : ySlow }}>
          {stars.map((star) => (
            <span
              key={star.id}
              className={`star ${star.kind === "plain" ? "" : star.kind}`.trim()}
              style={{ left: star.left, top: star.top, animationDelay: star.delay }}
            />
          ))}
        </motion.div>
      ) : (
        <motion.div className="grid-fx" style={{ y: reduce ? 0 : yMid }} />
      )}
      {palette === "a" ? <motion.div className="tiles" style={{ y: reduce ? 0 : yMid }} /> : null}
      <div className="scan" />
      <div className="vignette" />
    </div>
  );
}
