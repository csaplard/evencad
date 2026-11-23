// 3D viewer for the phone page. The shaft is a body of revolution, so the model is
// built straight from the half profile (x along the axis, radius) that the backend
// also uses for the STEP file. Drag to rotate, pinch or scroll to zoom.
// 'three' is mapped to a pinned CDN build by the import map in the page.
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'

const box = document.getElementById('viewer')
const note = document.getElementById('viewer-note')

async function main() {
  const res = await fetch(`/session/${box.dataset.session}/profile`)
  if (!res.ok) throw new Error(`profile: ${res.status}`)
  const { points, length, max_diameter: maxDiameter } = await res.json()
  if (points.length < 4) {
    note.textContent = 'No segments yet.'
    return
  }

  const renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  box.appendChild(renderer.domElement)

  const scene = new THREE.Scene()
  scene.background = new THREE.Color(0x000000)
  scene.add(new THREE.HemisphereLight(0xffffff, 0x223322, 1.1))
  const sun = new THREE.DirectionalLight(0xffffff, 2.2)
  sun.position.set(1, 2, 3)
  scene.add(sun)

  // LatheGeometry turns (radius, height) points around the Y axis.
  // The part is centred, then laid down so its axis is horizontal.
  // Each straight run of the profile is its own surface. One lathe over all points
  // would smooth the shading across the corners and make the steps look rounded.
  const outline = points.map(([x, r]) => new THREE.Vector2(r, x - length / 2))
  const steel = new THREE.MeshStandardMaterial({ color: 0x9aa7a0, metalness: 0.55, roughness: 0.45, side: THREE.DoubleSide })
  const part = new THREE.Group()
  for (let i = 0; i + 1 < outline.length; i++) {
    part.add(new THREE.Mesh(new THREE.LatheGeometry([outline[i], outline[i + 1]], 96), steel))
  }
  // Sharp edges (steps, chamfers) as bright circles, like the display on the glasses.
  const edgeLine = new THREE.LineBasicMaterial({ color: 0x33ff66 })
  for (const p of outline) {
    if (p.x <= 0) continue
    const circle = new THREE.EllipseCurve(0, 0, p.x, p.x).getPoints(96).map(c => new THREE.Vector3(c.x, p.y, c.y))
    part.add(new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(circle), edgeLine))
  }
  part.rotation.z = -Math.PI / 2
  scene.add(part)

  const size = Math.max(length, maxDiameter)
  const camera = new THREE.PerspectiveCamera(28, 1, size / 100, size * 20)
  camera.position.set(size * 0.7, size * 0.55, size * 1.5)

  const controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.enablePan = false
  controls.minDistance = size * 0.4
  controls.maxDistance = size * 6

  function resize() {
    const w = box.clientWidth
    const h = Math.round(w * 0.62)
    renderer.setSize(w, h)
    camera.aspect = w / h
    camera.updateProjectionMatrix()
  }
  resize()
  window.addEventListener('resize', resize)

  renderer.setAnimationLoop(() => {
    controls.update()
    renderer.render(scene, camera)
  })
  note.textContent = 'Drag to rotate. Pinch or scroll to zoom.'
  window.evencadViewerReady = true // used by the manual browser check
}

main().catch(err => {
  // The 2D side view below still shows the part.
  console.error(err)
  note.textContent = '3D view is not available here.'
})
