const dialog = document.querySelector(".lightbox");
const lightboxImage = dialog?.querySelector("img");
const lightboxTitle = dialog?.querySelector("h3");
const lightboxText = dialog?.querySelector("p");
const lightboxPrev = dialog?.querySelector(".lightbox-prev");
const lightboxNext = dialog?.querySelector(".lightbox-next");

let gallery = [];
let index = 0;

function showShot(nextIndex) {
  if (!gallery.length || !dialog || !lightboxImage) return;
  index = (nextIndex + gallery.length) % gallery.length;
  const button = gallery[index];
  lightboxImage.src = button.dataset.full || button.querySelector("img")?.src || "";
  lightboxImage.alt = button.dataset.title || "";
  if (lightboxTitle) lightboxTitle.textContent = button.dataset.title || "";
  if (lightboxText) lightboxText.textContent = button.dataset.text || "";
  const single = gallery.length < 2;
  if (lightboxPrev) lightboxPrev.hidden = single;
  if (lightboxNext) lightboxNext.hidden = single;
}

document.querySelectorAll(".shot").forEach((button) => {
  button.addEventListener("click", () => {
    if (!dialog || !lightboxImage) return;
    const strip = button.closest("[data-strip]");
    gallery = strip ? [...strip.querySelectorAll(".shot")] : [...document.querySelectorAll(".shot")];
    showShot(Math.max(0, gallery.indexOf(button)));
    dialog.showModal();
  });
});

document.querySelectorAll(".study-shot").forEach((button) => {
  button.addEventListener("click", () => {
    if (!dialog || !lightboxImage) return;
    const section = button.closest(".study");
    gallery = section ? [...section.querySelectorAll(".study-shot")] : [button];
    showShot(Math.max(0, gallery.indexOf(button)));
    dialog.showModal();
  });
});

lightboxPrev?.addEventListener("click", () => showShot(index - 1));
lightboxNext?.addEventListener("click", () => showShot(index + 1));

dialog?.querySelector(".lightbox-close")?.addEventListener("click", () => {
  dialog.close();
});

dialog?.addEventListener("click", (event) => {
  if (event.target === dialog) dialog.close();
});

dialog?.addEventListener("close", () => {
  if (lightboxImage) lightboxImage.src = "";
});

dialog?.addEventListener("keydown", (event) => {
  if (event.key === "ArrowLeft") {
    event.preventDefault();
    showShot(index - 1);
  } else if (event.key === "ArrowRight") {
    event.preventDefault();
    showShot(index + 1);
  }
});

document.querySelectorAll("[data-strip]").forEach((strip) => {
  const scroller = strip.querySelector(".strip");
  const prev = strip.querySelector(".strip-prev");
  const next = strip.querySelector(".strip-next");
  if (!scroller || !prev || !next) return;

  const step = () => {
    const item = scroller.querySelector("li");
    if (!item) return 198;
    const styles = getComputedStyle(scroller);
    const gap = parseFloat(styles.columnGap || styles.gap) || 10;
    return item.getBoundingClientRect().width + gap;
  };

  const update = () => {
    const max = scroller.scrollWidth - scroller.clientWidth - 2;
    prev.hidden = scroller.scrollLeft <= 2;
    next.hidden = max <= 2 || scroller.scrollLeft >= max;
  };

  const move = (direction) => {
    const left = Math.max(0, scroller.scrollLeft + direction * step());
    scroller.scrollTo({ left, behavior: "smooth" });
  };

  next.addEventListener("click", () => move(1));
  prev.addEventListener("click", () => move(-1));
  scroller.addEventListener("scroll", update, { passive: true });
  window.addEventListener("resize", update);
  update();
});

document.querySelectorAll("[data-slideshow]").forEach((slideshow) => {
  const track = slideshow.querySelector(".slide-track");
  const slides = [...slideshow.querySelectorAll(".slide")];
  const count = slideshow.querySelector(".slide-count");
  const shots = [...slideshow.querySelectorAll(".slide-shot")];
  let current = 0;

  const show = (nextIndex) => {
    current = (nextIndex + slides.length) % slides.length;
    track.style.transform = `translateX(-${current * 100}%)`;
    if (count) count.textContent = `${current + 1}/${slides.length}`;
  };

  slideshow.querySelector(".slide-prev")?.addEventListener("click", () => show(current - 1));
  slideshow.querySelector(".slide-next")?.addEventListener("click", () => show(current + 1));

  shots.forEach((button) => {
    button.addEventListener("click", () => {
      if (!dialog || !lightboxImage) return;
      gallery = shots;
      showShot(Math.max(0, shots.indexOf(button)));
      dialog.showModal();
    });
  });

  show(0);
});
