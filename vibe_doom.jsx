import { useEffect, useRef, useState, useCallback } from "react";

// ─────────────────────────────────────────────────────────────────────────────
// CONSTANTS
// ─────────────────────────────────────────────────────────────────────────────
const W = 640, H = 400;
const HALF_H = H / 2;
const FOV = Math.PI / 3;
const NUM_RAYS = W / 2;          // cast one ray per 2px column → 320 rays
const MAX_DIST = 20;
const PLAYER_SPEED = 0.05;
const ROT_SPEED = 0.035;
const MOUSE_SENSITIVITY = 0.0015;

// Map legend: ' '=floor, '#'=wall, 'E'=exit, 'e'=enemy spawn
const LEVELS = [
  [
    "###########",
    "#.........#",
    "#.###.###.#",
    "#.#...#...#",
    "#.#.#.#.###",
    "#...#.....#",
    "###.#####.#",
    "#.........#",
    "#.###.#.#.#",
    "#e..#...#E#",
    "###########",
  ],
  [
    "############",
    "#..........#",
    "#.##.####..#",
    "#..#.#....##",
    "##.#.#.##..#",
    "#..#...#...#",
    "#.####.#.#.#",
    "#......#.#.#",
    "#.####.#...#",
    "#e.....####E",
    "############",
  ],
  [
    "#############",
    "#...........#",
    "#.#########.#",
    "#.#.......#.#",
    "#.#.#####.#.#",
    "#.#.#...#.#.#",
    "#.#.#.e.#.#.#",
    "#.#.#####.#.#",
    "#.#.......#.#",
    "#.#########.#",
    "#e..........#",
    "#..........E#",
    "#############",
  ],
];

// Texture patterns for walls (4 shades)
function makeWallTexture(seed) {
  const data = new Uint8ClampedArray(64 * 64 * 4);
  let s = seed;
  const lcg = () => { s = (s * 1664525 + 1013904223) & 0xffffffff; return (s >>> 0) / 4294967296; };
  for (let y = 0; y < 64; y++) {
    for (let x = 0; x < 64; x++) {
      const i = (y * 64 + x) * 4;
      const noise = lcg() * 0.15;
      // brick pattern
      const bx = x % 16, by = y % 8;
      const grout = (bx === 0 || by === 0 || (by < 2 && Math.floor(y / 8) % 2 === 0 ? bx === 8 : bx === 8)) ? 0.5 : 1;
      const base = (0.55 + noise) * grout;
      data[i]   = Math.min(255, 180 * base);
      data[i+1] = Math.min(255, 90  * base);
      data[i+2] = Math.min(255, 40  * base);
      data[i+3] = 255;
    }
  }
  return data;
}

function makeFloorTexture() {
  const data = new Uint8ClampedArray(64 * 64 * 4);
  for (let y = 0; y < 64; y++) {
    for (let x = 0; x < 64; x++) {
      const i = (y * 64 + x) * 4;
      const tile = ((Math.floor(x / 16) + Math.floor(y / 16)) % 2 === 0) ? 0.18 : 0.14;
      data[i]   = 255 * tile;
      data[i+1] = 255 * tile;
      data[i+2] = 255 * tile;
      data[i+3] = 255;
    }
  }
  return data;
}

// ─────────────────────────────────────────────────────────────────────────────
// ENEMY AI (simple)
// ─────────────────────────────────────────────────────────────────────────────
class Enemy {
  constructor(x, y) {
    this.x = x + 0.5;
    this.y = y + 0.5;
    this.hp = 3;
    this.alive = true;
    this.lastMoveTimer = 0;
    this.dx = 0; this.dy = 0;
    this.visible = false;
    this.dist = 0;
  }
  update(player, map) {
    if (!this.alive) return;
    this.lastMoveTimer++;
    const eDx = player.x - this.x, eDy = player.y - this.y;
    this.dist = Math.hypot(eDx, eDy);
    if (this.dist < 0.5) { /* too close */ return; }
    if (this.lastMoveTimer % 2 === 0 && this.dist < 8) {
      const speed = 0.025;
      const nx = this.x + (eDx / this.dist) * speed;
      const ny = this.y + (eDy / this.dist) * speed;
      const mi = Math.floor(ny), mj = Math.floor(nx);
      if (map[mi]?.[mj] !== '#') { this.x = nx; this.y = ny; }
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// RAYCASTER
// ─────────────────────────────────────────────────────────────────────────────
function castRay(px, py, angle, map) {
  const sinA = Math.sin(angle), cosA = Math.cos(angle);
  for (let depth = 0.01; depth < MAX_DIST; depth += 0.04) {
    const tx = px + cosA * depth;
    const ty = py + sinA * depth;
    const mx = Math.floor(tx), my = Math.floor(ty);
    if (map[my]?.[mx] === '#') {
      // wall hit — figure out texture X
      const hitX = tx - Math.floor(tx);
      const hitY = ty - Math.floor(ty);
      const texX = Math.abs(cosA) > Math.abs(sinA) ? hitY : hitX;
      return { dist: depth, texX: Math.floor(texX * 64), side: Math.abs(cosA) > Math.abs(sinA) ? 1 : 0 };
    }
    if (map[my]?.[mx] === 'E') {
      return { dist: depth, texX: 0, side: 0, exit: true };
    }
  }
  return { dist: MAX_DIST, texX: 0, side: 0 };
}

// ─────────────────────────────────────────────────────────────────────────────
// MAIN COMPONENT
// ─────────────────────────────────────────────────────────────────────────────
export default function VibeDoom() {
  const canvasRef = useRef(null);
  const gameRef = useRef(null);
  const [screen, setScreen] = useState("title"); // title | playing | dead | win
  const [hud, setHud] = useState({ hp: 100, ammo: 30, level: 0, kills: 0 });
  const [message, setMessage] = useState("");
  const msgTimer = useRef(null);

  const showMsg = (txt) => {
    setMessage(txt);
    clearTimeout(msgTimer.current);
    msgTimer.current = setTimeout(() => setMessage(""), 2500);
  };

  const initLevel = useCallback((lvlIdx) => {
    const mapRaw = LEVELS[lvlIdx];
    const map = mapRaw.map(r => r.split(''));

    // Find player start (first open cell)
    let px = 1.5, py = 1.5;
    const enemies = [];
    for (let y = 0; y < map.length; y++) {
      for (let x = 0; x < map[y].length; x++) {
        if (map[y][x] === '.') { px = x + 0.5; py = y + 0.5; map[y][x] = '.'; }
        else if (map[y][x] === 'e') { enemies.push(new Enemy(x, y)); map[y][x] = '.'; }
        else if (map[y][x] === 'E') { /* keep marker */ }
      }
    }

    const wallTex = makeWallTexture(42 + lvlIdx * 7);
    const floorTex = makeFloorTexture();

    gameRef.current = {
      map,
      mapRaw,
      player: { x: px, y: py, angle: 0 },
      enemies,
      bullets: [],
      zbuf: new Float32Array(NUM_RAYS),
      keys: {},
      mouse: { dx: 0 },
      hp: 100,
      ammo: 30,
      kills: 0,
      lvl: lvlIdx,
      wallTex,
      floorTex,
      shootTimer: 0,
      muzzleFlash: 0,
      locked: false,
    };
  }, []);

  // ── RENDER LOOP ────────────────────────────────────────────────────────────
  useEffect(() => {
    if (screen !== "playing") return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d", { willReadFrequently: false });
    const imgData = ctx.createImageData(W, H);
    const pixels = imgData.data;

    let raf;
    let lastTime = performance.now();

    const loop = (now) => {
      const dt = Math.min((now - lastTime) / 16.67, 3);
      lastTime = now;
      const g = gameRef.current;
      if (!g) { raf = requestAnimationFrame(loop); return; }

      // ── INPUT ──
      const { keys, player, map } = g;

      // Mouse look
      player.angle += g.mouse.dx * MOUSE_SENSITIVITY;
      g.mouse.dx = 0;

      let mx = 0, my = 0;
      const spd = PLAYER_SPEED * dt;
      if (keys["w"] || keys["arrowup"])    { mx += Math.cos(player.angle) * spd; my += Math.sin(player.angle) * spd; }
      if (keys["s"] || keys["arrowdown"])  { mx -= Math.cos(player.angle) * spd; my -= Math.sin(player.angle) * spd; }
      if (keys["a"])                        { mx += Math.cos(player.angle - Math.PI/2) * spd; my += Math.sin(player.angle - Math.PI/2) * spd; }
      if (keys["d"])                        { mx -= Math.cos(player.angle - Math.PI/2) * spd; my -= Math.sin(player.angle - Math.PI/2) * spd; }
      if (keys["arrowleft"])  player.angle -= ROT_SPEED * dt;
      if (keys["arrowright"]) player.angle += ROT_SPEED * dt;

      const nx = player.x + mx, ny = player.y + my;
      if (map[Math.floor(player.y)]?.[Math.floor(nx)] !== '#') player.x = nx;
      if (map[Math.floor(ny)]?.[Math.floor(player.x)] !== '#') player.y = ny;

      // Shoot
      if (g.shootTimer > 0) g.shootTimer -= dt;
      if (g.muzzleFlash > 0) g.muzzleFlash -= dt;

      // ── RENDER SKY / FLOOR ──
      for (let y = 0; y < H; y++) {
        const isCeiling = y < HALF_H;
        if (isCeiling) {
          // sky gradient
          const t = y / HALF_H;
          const r = Math.floor(20 + t * 10);
          const g2 = Math.floor(5 + t * 5);
          for (let x = 0; x < W; x++) {
            const i = (y * W + x) * 4;
            pixels[i] = r; pixels[i+1] = g2; pixels[i+2] = 10; pixels[i+3] = 255;
          }
        } else {
          // floor with texture
          const rowAngle = Math.PI / 2;
          const rowDist = HALF_H / (y - HALF_H + 0.001);
          const floorStepX = rowDist * (Math.cos(player.angle + FOV / 2) - Math.cos(player.angle - FOV / 2)) / W;
          const floorStepY = rowDist * (Math.sin(player.angle + FOV / 2) - Math.sin(player.angle - FOV / 2)) / W;
          let fx = player.x + rowDist * Math.cos(player.angle - FOV / 2);
          let fy = player.y + rowDist * Math.sin(player.angle - FOV / 2);
          for (let x = 0; x < W; x++) {
            const tx = Math.floor((fx - Math.floor(fx)) * 64) & 63;
            const ty = Math.floor((fy - Math.floor(fy)) * 64) & 63;
            const ti = (ty * 64 + tx) * 4;
            const dist = rowDist;
            const dark = Math.max(0, 1 - dist / MAX_DIST);
            const i = (y * W + x) * 4;
            pixels[i]   = g.floorTex[ti]   * dark;
            pixels[i+1] = g.floorTex[ti+1] * dark;
            pixels[i+2] = g.floorTex[ti+2] * dark;
            pixels[i+3] = 255;
            fx += floorStepX; fy += floorStepY;
          }
        }
      }

      // ── RAYCASTING WALLS ──
      for (let col = 0; col < NUM_RAYS; col++) {
        const angle = player.angle - FOV / 2 + (col / NUM_RAYS) * FOV;
        const { dist, texX, side, exit } = castRay(player.x, player.y, angle, map);
        g.zbuf[col] = dist;

        const correctedDist = dist * Math.cos(angle - player.angle);
        const wallH = Math.min(H, (H / correctedDist) * 0.8);
        const wallTop = Math.floor(HALF_H - wallH / 2);
        const wallBot = Math.floor(HALF_H + wallH / 2);
        const shade = side === 1 ? 0.7 : 1.0;
        const darkness = Math.max(0, 1 - dist / MAX_DIST);

        for (let y = wallTop; y < wallBot; y++) {
          const texY = Math.floor(((y - wallTop) / wallH) * 64) & 63;
          const ti = (texY * 64 + texX) * 4;
          const i = (y * W + col * 2) * 4;
          const i2 = (y * W + col * 2 + 1) * 4;
          if (exit) {
            // exit door: bright green
            pixels[i]   = pixels[i2]   = 10 * darkness;
            pixels[i+1] = pixels[i2+1] = 200 * darkness;
            pixels[i+2] = pixels[i2+2] = 10 * darkness;
          } else {
            pixels[i]   = pixels[i2]   = g.wallTex[ti]   * shade * darkness;
            pixels[i+1] = pixels[i2+1] = g.wallTex[ti+1] * shade * darkness;
            pixels[i+2] = pixels[i2+2] = g.wallTex[ti+2] * shade * darkness;
          }
          pixels[i+3] = pixels[i2+3] = 255;
        }
      }

      // ── ENEMIES ──
      g.enemies.forEach(en => {
        en.update(player, map);
        if (!en.alive) return;

        // enemy harms player if close
        if (en.dist < 0.75 && Math.random() < 0.008 * dt) {
          g.hp -= 5;
          showMsg("AARGH!");
          if (g.hp <= 0) { setScreen("dead"); return; }
        }

        // sprite projection
        const spriteDx = en.x - player.x, spriteDy = en.y - player.y;
        const sprDist = Math.hypot(spriteDx, spriteDy);
        if (sprDist < 0.1) return;

        const sprAngle = Math.atan2(spriteDy, spriteDx) - player.angle;
        let sa = sprAngle;
        while (sa > Math.PI) sa -= Math.PI * 2;
        while (sa < -Math.PI) sa += Math.PI * 2;

        if (Math.abs(sa) < FOV / 1.5) {
          const sprH = Math.min(H, (H / sprDist) * 0.8);
          const sprTop = Math.floor(HALF_H - sprH / 2);
          const sprBot = Math.floor(HALF_H + sprH / 2);
          const sprScreenX = Math.floor((0.5 + sa / FOV) * W);
          const sprW = sprH;
          const startX = Math.floor(sprScreenX - sprW / 2);
          const dark = Math.max(0, 1 - sprDist / MAX_DIST);

          for (let sx = 0; sx < sprW; sx++) {
            const px2 = startX + sx;
            const col = Math.floor(px2 / 2);
            if (px2 < 0 || px2 >= W) continue;
            if (g.zbuf[col] <= sprDist) continue;

            const u = sx / sprW;
            for (let sy = sprTop; sy < sprBot; sy++) {
              if (sy < 0 || sy >= H) continue;
              const v = (sy - sprTop) / sprH;
              const i = (sy * W + px2) * 4;
              // skull-like sprite: eyes + body
              const gx = u - 0.5, gy = v - 0.45;
              const inBody = Math.abs(gx) < 0.35 && v > 0.25 && v < 0.95;
              const inHead = (gx * gx + gy * gy) < 0.07;
              const leftEye = Math.hypot(gx + 0.1, gy + 0.05) < 0.04;
              const rightEye = Math.hypot(gx - 0.1, gy + 0.05) < 0.04;
              const mouth = Math.abs(gx) < 0.12 && v > 0.56 && v < 0.64;
              if (inHead || inBody) {
                pixels[i]   = (leftEye || rightEye || mouth) ? 220 : (inHead ? 170 : 100) * dark;
                pixels[i+1] = (leftEye || rightEye || mouth) ? 0   : (inHead ? 30  : 20)  * dark;
                pixels[i+2] = (leftEye || rightEye || mouth) ? 0   : (inHead ? 20  : 15)  * dark;
                pixels[i+3] = 255;
              }
            }
          }
        }
      });

      // ── BULLETS ──
      g.bullets = g.bullets.filter(b => b.life > 0);
      g.bullets.forEach(b => {
        b.x += Math.cos(b.angle) * 0.3 * dt;
        b.y += Math.sin(b.angle) * 0.3 * dt;
        b.life -= dt;
        if (map[Math.floor(b.y)]?.[Math.floor(b.x)] === '#') { b.life = 0; return; }

        // hit enemy
        g.enemies.forEach(en => {
          if (!en.alive) return;
          if (Math.hypot(en.x - b.x, en.y - b.y) < 0.4) {
            en.hp--;
            b.life = 0;
            if (en.hp <= 0) {
              en.alive = false;
              g.kills++;
              showMsg("ENEMY DOWN!");
            }
          }
        });
      });

      // Check exit
      const exitCell = map[Math.floor(player.y)]?.[Math.floor(player.x)];
      // Also check the raw char
      const ry = Math.floor(player.y), rx = Math.floor(player.x);
      if (g.mapRaw[ry]?.[rx]?.[0] === 'E' || (map[ry]?.[rx] === 'E')) {
        if (g.lvl + 1 < LEVELS.length) {
          initLevel(g.lvl + 1);
          showMsg(`LEVEL ${g.lvl + 2}`);
        } else {
          setScreen("win");
        }
      }

      // paint
      ctx.putImageData(imgData, 0, 0);

      // ── HUD ──
      // muzzle flash
      if (g.muzzleFlash > 0) {
        ctx.fillStyle = `rgba(255,200,50,${g.muzzleFlash * 0.4})`;
        ctx.fillRect(0, 0, W, H);
      }

      // Weapon
      drawWeapon(ctx, g.muzzleFlash > 0);

      // Status bars
      drawHUD(ctx, g.hp, g.ammo, g.kills, g.lvl + 1);

      setHud({ hp: g.hp, ammo: g.ammo, level: g.lvl + 1, kills: g.kills });

      raf = requestAnimationFrame(loop);
    };

    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [screen, initLevel]);

  // ── DRAW WEAPON ──────────────────────────────────────────────────────────
  function drawWeapon(ctx, flash) {
    const bx = W / 2, by = H - 20;
    // gun barrel
    ctx.fillStyle = "#555";
    ctx.fillRect(bx - 8, by - 80, 16, 80);
    // slide
    ctx.fillStyle = "#333";
    ctx.fillRect(bx - 14, by - 65, 28, 55);
    // trigger guard
    ctx.strokeStyle = "#444";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(bx - 10, by - 20);
    ctx.lineTo(bx - 10, by - 8);
    ctx.lineTo(bx + 10, by - 8);
    ctx.lineTo(bx + 10, by - 20);
    ctx.stroke();
    // handle
    ctx.fillStyle = "#222";
    ctx.fillRect(bx - 10, by - 15, 20, 35);
    // muzzle flash
    if (flash) {
      ctx.fillStyle = "rgba(255,220,50,0.85)";
      ctx.beginPath();
      ctx.arc(bx, by - 85, 18, 0, Math.PI * 2);
      ctx.fill();
    }
    // crosshair
    ctx.strokeStyle = "rgba(255,255,255,0.7)";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(bx - 12, HALF_H); ctx.lineTo(bx + 12, HALF_H);
    ctx.moveTo(bx, HALF_H - 12); ctx.lineTo(bx, HALF_H + 12);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(bx, HALF_H, 5, 0, Math.PI * 2);
    ctx.stroke();
  }

  // ── DRAW HUD ─────────────────────────────────────────────────────────────
  function drawHUD(ctx, hp, ammo, kills, level) {
    // bottom bar
    ctx.fillStyle = "rgba(0,0,0,0.65)";
    ctx.fillRect(0, H - 44, W, 44);

    ctx.font = "bold 14px monospace";
    // HP
    ctx.fillStyle = hp > 50 ? "#4f4" : hp > 25 ? "#ff4" : "#f44";
    ctx.fillText(`❤ HP: ${hp}`, 12, H - 14);
    // Ammo
    ctx.fillStyle = "#fa0";
    ctx.fillText(`⦿ AMMO: ${ammo}`, 140, H - 14);
    // Kills
    ctx.fillStyle = "#f44";
    ctx.fillText(`☠ KILLS: ${kills}`, 290, H - 14);
    // Level
    ctx.fillStyle = "#aaf";
    ctx.fillText(`LVL ${level}/3`, W - 80, H - 14);

    // HP bar
    ctx.fillStyle = "#333";
    ctx.fillRect(12, H - 28, 100, 8);
    ctx.fillStyle = hp > 50 ? "#4f4" : hp > 25 ? "#ff4" : "#f44";
    ctx.fillRect(12, H - 28, hp, 8);

    // Ammo bar
    ctx.fillStyle = "#333";
    ctx.fillRect(140, H - 28, 80, 8);
    ctx.fillStyle = "#fa0";
    ctx.fillRect(140, H - 28, (ammo / 30) * 80, 8);
  }

  // ── INPUT EVENTS ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (screen !== "playing") return;
    const g = () => gameRef.current;

    const onKey = (e, down) => {
      const k = e.key.toLowerCase();
      if (g()) g().keys[k] = down;
      if (down && (k === " " || k === "e") && g()) fireWeapon();
      e.preventDefault();
    };
    const onMouse = (e) => {
      if (g()) g().mouse.dx += e.movementX;
    };
    const onClick = () => {
      const canvas = canvasRef.current;
      if (canvas && !document.pointerLockElement) {
        canvas.requestPointerLock();
      } else {
        fireWeapon();
      }
    };

    const fireWeapon = () => {
      const state = g();
      if (!state) return;
      if (state.ammo <= 0) { showMsg("OUT OF AMMO!"); return; }
      if (state.shootTimer > 0) return;
      state.ammo--;
      state.shootTimer = 8;
      state.muzzleFlash = 4;
      const { player } = state;
      state.bullets.push({ x: player.x, y: player.y, angle: player.angle, life: 20 });

      // Reload pickup logic: every 0 ammo, restore
      if (state.ammo <= 0) {
        setTimeout(() => { if (g()) { g().ammo = 15; showMsg("RELOADED!"); } }, 1500);
      }
    };

    window.addEventListener("keydown", e => onKey(e, true));
    window.addEventListener("keyup",   e => onKey(e, false));
    document.addEventListener("mousemove", onMouse);
    canvasRef.current?.addEventListener("click", onClick);

    return () => {
      window.removeEventListener("keydown", e => onKey(e, true));
      window.removeEventListener("keyup",   e => onKey(e, false));
      document.removeEventListener("mousemove", onMouse);
      if (document.pointerLockElement) document.exitPointerLock();
    };
  }, [screen]);

  const startGame = () => {
    initLevel(0);
    setScreen("playing");
  };

  // ─────────────────────────────────────────────────────────────────────────
  // SCREENS
  // ─────────────────────────────────────────────────────────────────────────
  const titleStyle = {
    width: W, height: H, background: "#0a0008",
    display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
    fontFamily: "monospace", color: "#c0392b", userSelect: "none",
  };
  const btnStyle = {
    marginTop: 24, padding: "12px 40px", background: "#c0392b", color: "#fff",
    border: "none", fontSize: 18, fontFamily: "monospace", cursor: "pointer",
    letterSpacing: 4, textTransform: "uppercase",
    boxShadow: "0 0 20px #c0392b88",
  };

  if (screen === "title") return (
    <div style={titleStyle}>
      <div style={{ fontSize: 64, fontWeight: 900, letterSpacing: 8, textShadow: "0 0 30px #c0392b, 0 0 60px #c0392b88" }}>VIBE DOOM</div>
      <div style={{ fontSize: 14, color: "#666", marginTop: 8, letterSpacing: 3 }}>VIBE CODED BY CLAUDE SONNET 4.6</div>
      <div style={{ marginTop: 32, color: "#888", fontSize: 13, lineHeight: 2, textAlign: "center" }}>
        <span style={{ color: "#aaa" }}>WASD</span> — Move &nbsp;|&nbsp; <span style={{ color: "#aaa" }}>←→ / Mouse</span> — Turn<br/>
        <span style={{ color: "#aaa" }}>CLICK / SPACE</span> — Fire &nbsp;|&nbsp; Reach <span style={{ color: "#4f4" }}>GREEN DOOR</span> to advance<br/>
        <span style={{ color: "#f44" }}>Kill all demons</span> or die trying.
      </div>
      <button style={btnStyle} onClick={startGame}>▶ NEW GAME</button>
    </div>
  );

  if (screen === "dead") return (
    <div style={{ ...titleStyle, color: "#f00" }}>
      <div style={{ fontSize: 52, fontWeight: 900, textShadow: "0 0 40px #f00" }}>YOU DIED</div>
      <div style={{ marginTop: 16, color: "#888", fontSize: 14 }}>Kills: {hud.kills} | Level: {hud.level}/3</div>
      <button style={btnStyle} onClick={startGame}>↺ TRY AGAIN</button>
    </div>
  );

  if (screen === "win") return (
    <div style={{ ...titleStyle, color: "#0f0" }}>
      <div style={{ fontSize: 52, fontWeight: 900, textShadow: "0 0 40px #0f0" }}>YOU WIN!</div>
      <div style={{ marginTop: 16, color: "#aaa", fontSize: 14 }}>All 3 levels cleared! Kills: {hud.kills}</div>
      <button style={{ ...btnStyle, background: "#0a0" }} onClick={startGame}>↺ PLAY AGAIN</button>
    </div>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", background: "#000", minHeight: "100vh", padding: "12px 0" }}>
      <div style={{ position: "relative" }}>
        <canvas ref={canvasRef} width={W} height={H} style={{ display: "block", imageRendering: "pixelated", cursor: "none" }} />
        {message && (
          <div style={{
            position: "absolute", top: 20, left: "50%", transform: "translateX(-50%)",
            background: "rgba(0,0,0,0.75)", color: "#ff0", fontFamily: "monospace",
            fontSize: 18, padding: "6px 20px", letterSpacing: 3, pointerEvents: "none",
            textShadow: "0 0 8px #ff0",
          }}>{message}</div>
        )}
      </div>
      <div style={{ marginTop: 10, fontFamily: "monospace", color: "#555", fontSize: 12, letterSpacing: 2 }}>
        CLICK CANVAS TO LOCK MOUSE &nbsp;|&nbsp; ESC TO RELEASE
      </div>
    </div>
  );
}
