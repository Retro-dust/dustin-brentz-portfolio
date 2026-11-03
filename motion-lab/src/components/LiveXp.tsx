import { useRef } from "react";
import { useMotionValueEvent, type MotionValue } from "motion/react";
import { heroXpCap } from "../data";

const formatter = new Intl.NumberFormat("en-US");

export default function LiveXp({ progress }: { progress: MotionValue<number> }) {
  const ref = useRef<HTMLSpanElement>(null);
  useMotionValueEvent(progress, "change", (latest) => {
    if (ref.current) {
      ref.current.textContent = formatter.format(Math.min(heroXpCap, Math.round(6800 + latest * 3200)));
    }
  });
  return <span ref={ref}>6,800</span>;
}
