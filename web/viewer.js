import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

export class ModelViewer {
  constructor(container) {
    this.container = container;
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(35, 1, 0.0001, 1000);
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.renderer.setClearColor(0x000000, 0);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.0;
    this.container.prepend(this.renderer.domElement);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.autoRotate = !matchMedia('(prefers-reduced-motion: reduce)').matches;
    this.controls.autoRotateSpeed = 1.2;
    this.scene.add(new THREE.HemisphereLight(0xf4ffe3, 0x34402e, 1.6));
    this.scene.add(new THREE.AmbientLight(0xffffff, 0.4));
    const key = new THREE.DirectionalLight(0xfff8df, 2);
    key.position.set(3, 5, 4);
    this.scene.add(key);
    const rim = new THREE.DirectionalLight(0xb1d1ff, 1.4);
    rim.position.set(-3, 1, -2);
    this.scene.add(rim);
    this.material = new THREE.MeshStandardMaterial({ color: '#c1f777', metalness: 0.14, roughness: 0.5, side: THREE.DoubleSide });
    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(container);
    this.resize();
    this.renderer.setAnimationLoop(() => {
      if (!this.model || document.hidden || !this.container.offsetParent) return;
      this.controls.update();
      this.renderer.render(this.scene, this.camera);
    });
  }

  resize() {
    const { clientWidth: w, clientHeight: h } = this.container;
    if (!w || !h) return;
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h);
  }

  clear() {
    if (this.model) {
      this.scene.remove(this.model);
      this.model.traverse(child => { if (child.isMesh) child.geometry.dispose(); });
      this.model = null;
    }
    this.renderer.clear();
  }

  async load(url) {
    const request = this.request = (this.request || 0) + 1;
    const gltf = await new GLTFLoader().loadAsync(url);
    if (request !== this.request) {
      gltf.scene.traverse(child => { if (child.isMesh) {child.geometry.dispose(); child.material.dispose();} });
      return false;
    }
    this.clear();
    this.model = gltf.scene;
    this.model.traverse(child => {
      if (child.isMesh) {
        child.geometry.computeVertexNormals();
        const old = child.material;
        if (Array.isArray(old)) old.forEach(material => material.dispose()); else old.dispose();
        child.material = this.material;
      }
    });
    this.scene.add(this.model);
    this.reset();
    return true;
  }

  reset(direction = 'perspective') {
    if (!this.model) return;
    const box = new THREE.Box3().setFromObject(this.model);
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const radius = Math.max(size.x, size.y, size.z) || .1;
    const distance = radius / (2 * Math.tan(THREE.MathUtils.degToRad(this.camera.fov / 2))) * Math.max(1, 1 / this.camera.aspect) * 1.35;
    this.controls.target.copy(center);
    const angles = { perspective: [1, .6, 1.4], front: [0, 0, 1], side: [1, 0, 0], back: [0, 0, -1] };
    this.camera.position.copy(center).add(new THREE.Vector3(...(angles[direction] || angles.perspective)).normalize().multiplyScalar(distance));
    this.camera.near = radius / 1000;
    this.camera.far = radius * 1000;
    this.camera.updateProjectionMatrix();
    this.controls.minDistance = radius * .2;
    this.controls.maxDistance = radius * 12;
    this.controls.update();
  }
}
