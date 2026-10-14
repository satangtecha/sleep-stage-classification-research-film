"use strict";
// Presentation controls only. No notebook execution, polling, training, or API writes.
const menu = document.getElementById("chapterNav");
const menuToggle = document.getElementById("menuToggle");
const themeToggle = document.getElementById("themeToggle");
const codeToggle = document.getElementById("codeToggle");
const sourceBlocks = [...document.querySelectorAll("details.source-code")];
const chapterLinks = [...document.querySelectorAll(".chapter-link")];

function setTheme(dark) {
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  themeToggle.textContent = dark ? "โหมดสว่าง" : "โหมดมืด";
  themeToggle.setAttribute("aria-pressed", String(dark));
}
// New palette defaults to the requested charcoal theme, not the old green preference.
const themeStorageKey = "sleep-stage-course-neutral-theme-v1";
try { setTheme(localStorage.getItem(themeStorageKey) !== "light"); } catch { setTheme(true); }
themeToggle.addEventListener("click", () => {
  const dark = document.documentElement.dataset.theme !== "dark";
  setTheme(dark);
  try { localStorage.setItem(themeStorageKey, dark ? "dark" : "light"); } catch { /* storage may be disabled */ }
});
menuToggle.addEventListener("click", () => {
  const open = menu.classList.toggle("is-open");
  menuToggle.setAttribute("aria-expanded", String(open));
});
function closeMenu() { menu.classList.remove("is-open"); menuToggle.setAttribute("aria-expanded", "false"); }
document.addEventListener("keydown", (event) => { if (event.key === "Escape" && menu.classList.contains("is-open")) { closeMenu(); menuToggle.focus(); } });
menu.addEventListener("click", (event) => { if (event.target.closest("a")) closeMenu(); });
codeToggle.addEventListener("click", () => {
  const open = !sourceBlocks.every((block) => block.open);
  for (const block of sourceBlocks) block.open = open;
  codeToggle.textContent = open ? "ซ่อนโค้ดทั้งหมด" : "แสดงโค้ดทั้งหมด";
  codeToggle.setAttribute("aria-pressed", String(open));
});
for (const block of sourceBlocks) block.addEventListener("toggle", () => {
  const allOpen = sourceBlocks.every((source) => source.open);
  codeToggle.textContent = allOpen ? "ซ่อนโค้ดทั้งหมด" : "แสดงโค้ดทั้งหมด";
  codeToggle.setAttribute("aria-pressed", String(allOpen));
});
const chapters = [...document.querySelectorAll("article.chapter")];
let scheduled = false;
function markChapter() {
  const active = chapters.reduce((current, chapter) => chapter.getBoundingClientRect().top <= 150 ? chapter : current, chapters[0]);
  for (const link of chapterLinks) {
    if (link.hash === `#${active.id}`) link.setAttribute("aria-current", "location");
    else link.removeAttribute("aria-current");
  }
  scheduled = false;
}
window.addEventListener("scroll", () => { if (!scheduled) { scheduled = true; requestAnimationFrame(markChapter); } }, { passive: true });
markChapter();
