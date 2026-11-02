"use client";

import { OrbitControls } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef, type MutableRefObject, type RefObject } from "react";
import * as THREE from "three";
import { planeSize } from "@/lib/geometry";
import { fileUrl } from "@/lib/utils";

export type LensMode = "original" | "observed" | "inferred" | "generated" | "testimony" | "all";

type SceneProps = {
  width: number;
  height: number;
  photo: string;
  depth: string;
  entityIds: string;
  unknown: string;
  generated: string;
  testimony: string;
  motion: string;
  hypothesis: string | null;
  lens: LensMode;
  depthAmount: number;
  motionOn: boolean;
  highlightUv: [number, number] | null;
  onSelectIndex: (index: number) => void;
};

const vertex = /* glsl */ `
  varying vec2 vUv;
  uniform sampler2D uDepth;
  uniform sampler2D uMotion;
  uniform float uDepthScale;
  uniform float uTime;
  uniform float uMotionOn;
  void main() {
    vUv = uv;
    float depth = texture2D(uDepth, uv).r;
    float motion = texture2D(uMotion, uv).r * uMotionOn;
    vec3 displaced = position;
    displaced.z += depth * uDepthScale;
    float wave = sin(uv.y * 48.0 + uTime * 1.4) * 0.012 * motion;
    displaced.x += wave;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(displaced, 1.0);
  }
`;

const fragment = /* glsl */ `
  varying vec2 vUv;
  uniform sampler2D uPhoto;
  uniform sampler2D uDepth;
  uniform sampler2D uUnknown;
  uniform sampler2D uGenerated;
  uniform sampler2D uTestimony;
  uniform sampler2D uHypothesis;
  uniform float uHasHypothesis;
  uniform int uMode;
  uniform float uTime;
  uniform float uHighlight;
  uniform vec2 uHighlightUv;
  void main() {
    vec3 photo = texture2D(uPhoto, vUv).rgb;
    float depth = texture2D(uDepth, vUv).r;
    float unknown = texture2D(uUnknown, vUv).r;
    float generated = max(texture2D(uGenerated, vUv).r, texture2D(uHypothesis, vUv).a * uHasHypothesis);
    float testimony = texture2D(uTestimony, vUv).r;
    vec3 hyp = texture2D(uHypothesis, vUv).rgb;
    vec3 color = photo;
    if (uHasHypothesis > 0.5 && texture2D(uHypothesis, vUv).a > 0.4) color = hyp;
    vec3 inferred = mix(vec3(0.08, 0.1, 0.14), vec3(0.56, 0.75, 1.0), depth);
    vec3 violet = vec3(0.72, 0.62, 0.9);
    vec3 amber = vec3(0.89, 0.64, 0.36);
    vec3 ash = vec3(0.45, 0.43, 0.4);
    if (uMode == 0) {
      color = photo;
    } else if (uMode == 1) {
      color = mix(photo, ash, unknown * 0.9);
      color = mix(color, vec3(0.02), generated);
    } else if (uMode == 2) {
      float luma = dot(photo, vec3(0.3, 0.59, 0.11));
      color = inferred * (0.75 + 0.35 * luma);
    } else if (uMode == 3) {
      color = photo * 0.22;
      color = mix(color, ash, unknown * (1.0 - generated));
      color = mix(color, violet, generated);
    } else if (uMode == 4) {
      color = photo * 0.55;
      color = mix(color, amber, testimony);
    } else {
      color = mix(color, inferred, 0.18);
      color = mix(color, violet, generated * 0.9);
      color = mix(color, amber, testimony * 0.85);
      color = mix(color, ash, unknown * 0.55 * (1.0 - generated));
    }
    if (uHighlight > 0.5) {
      float dist = distance(vUv, uHighlightUv);
      float ring = smoothstep(0.012, 0.0, abs(dist - 0.055));
      color = mix(color, vec3(0.97, 0.93, 0.84), ring);
    }
    gl_FragColor = vec4(color, 1.0);
  }
`;

function PhotoMesh(props: SceneProps & { idMap: MutableRefObject<Uint8Array | null> }) {
  const material = useRef<THREE.ShaderMaterial>(null);
  const size = planeSize(props.width, props.height);
  const geometry = useMemo(
    () => new THREE.PlaneGeometry(size.width, size.height, 180, 120),
    [size.width, size.height],
  );
  const textures = useMemo(() => {
    const loader = new THREE.TextureLoader();
    const load = (url: string) => {
      const texture = loader.load(url);
      texture.colorSpace = THREE.SRGBColorSpace;
      texture.minFilter = THREE.LinearFilter;
      return texture;
    };
    const data = (url: string) => {
      const texture = loader.load(url);
      texture.colorSpace = THREE.NoColorSpace;
      texture.minFilter = THREE.LinearFilter;
      return texture;
    };
    return {
      photo: load(props.photo),
      depth: data(props.depth),
      unknown: data(props.unknown),
      generated: data(props.generated),
      testimony: data(props.testimony),
      motion: data(props.motion),
      hypothesis: props.hypothesis ? load(props.hypothesis) : data(props.unknown),
    };
  }, [props.photo, props.depth, props.unknown, props.generated, props.testimony, props.motion, props.hypothesis]);

  useEffect(() => {
    return () => {
      geometry.dispose();
      Object.values(textures).forEach((texture) => texture.dispose());
    };
  }, [geometry, textures]);

  useFrame((state) => {
    const uniforms = material.current?.uniforms;
    if (!uniforms) return;
    uniforms.uTime.value = state.clock.elapsedTime;
    uniforms.uDepthScale.value = scale;
    uniforms.uMotionOn.value = props.motionOn ? 1 : 0;
    uniforms.uMode.value = ["original", "observed", "inferred", "generated", "testimony", "all"].indexOf(props.lens);
    uniforms.uHasHypothesis.value = props.hypothesis ? 1 : 0;
    uniforms.uHighlight.value = props.highlightUv ? 1 : 0;
    uniforms.uHighlightUv.value.set(...(props.highlightUv || [0.5, 0.5]));
    uniforms.uHypothesis.value = textures.hypothesis;
  });

  const scale = props.lens === "original" ? 0 : props.depthAmount * 0.48;
  return (
    <mesh
      geometry={geometry}
      onClick={(event) => {
        const uv = event.uv;
        const map = props.idMap.current;
        if (!uv || !map) return;
        const x = Math.min(props.width - 1, Math.max(0, Math.round(uv.x * (props.width - 1))));
        const y = Math.min(props.height - 1, Math.max(0, Math.round((1 - uv.y) * (props.height - 1))));
        props.onSelectIndex(map[y * props.width + x] || 0);
      }}
    >
      <shaderMaterial
        ref={material}
        vertexShader={vertex}
        fragmentShader={fragment}
        uniforms={{
          uPhoto: { value: textures.photo },
          uDepth: { value: textures.depth },
          uUnknown: { value: textures.unknown },
          uGenerated: { value: textures.generated },
          uTestimony: { value: textures.testimony },
          uMotion: { value: textures.motion },
          uHypothesis: { value: textures.hypothesis },
          uHasHypothesis: { value: props.hypothesis ? 1 : 0 },
          uDepthScale: { value: scale },
          uTime: { value: 0 },
          uMotionOn: { value: props.motionOn ? 1 : 0 },
          uMode: { value: ["original", "observed", "inferred", "generated", "testimony", "all"].indexOf(props.lens) },
          uHighlight: { value: props.highlightUv ? 1 : 0 },
          uHighlightUv: { value: new THREE.Vector2(...(props.highlightUv || [0.5, 0.5])) },
        }}
      />
    </mesh>
  );
}

export function LivingScene(props: SceneProps) {
  const ids = useRef<Uint8Array | null>(null);
  const fps = useRef<HTMLSpanElement>(null);
  const frames = useRef(0);
  const last = useRef(performance.now());

  useEffect(() => {
    let cancelled = false;
    const image = new Image();
    image.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = props.width;
      canvas.height = props.height;
      const ctx = canvas.getContext("2d", { willReadFrequently: true });
      if (!ctx) return;
      ctx.drawImage(image, 0, 0, props.width, props.height);
      const data = ctx.getImageData(0, 0, props.width, props.height).data;
      const packed = new Uint8Array(props.width * props.height);
      for (let i = 0; i < packed.length; i++) packed[i] = data[i * 4];
      if (!cancelled) ids.current = packed;
    };
    image.src = props.entityIds;
    return () => {
      cancelled = true;
    };
  }, [props.entityIds, props.width, props.height]);

  return (
    <div className="relative h-full min-h-[420px] w-full">
      <Canvas
        camera={{ position: [0, 0.02, 1.72], fov: 36 }}
        dpr={[1, 1.6]}
        gl={{ antialias: true }}
        onCreated={({ gl }) => {
          gl.setClearColor("#0c0b0a");
        }}
      >
        <FpsCounter fpsRef={fps} frames={frames} last={last} />
        <PhotoMesh {...props} idMap={ids} />
        <OrbitControls
          makeDefault
          enablePan={false}
          minAzimuthAngle={-0.42}
          maxAzimuthAngle={0.42}
          minPolarAngle={Math.PI / 2 - 0.28}
          maxPolarAngle={Math.PI / 2 + 0.2}
          minDistance={1.25}
          maxDistance={2.15}
        />
        <FocusRig uv={props.highlightUv} width={props.width} height={props.height} />
      </Canvas>
      <div className="pointer-events-none absolute bottom-3 right-3 rounded-full bg-black/40 px-3 py-1 text-[11px] text-[var(--muted)]">
        <span ref={fps}>–</span> fps · drag to look, within the evidence cone
      </div>
    </div>
  );
}

function FocusRig({ uv, width, height }: { uv: [number, number] | null; width: number; height: number }) {
  const size = planeSize(width, height);
  const desired = useMemo(() => new THREE.Vector3(), []);
  useFrame((state) => {
    const orbit = state.controls as { target?: THREE.Vector3 } | null;
    if (!uv || !orbit?.target) return;
    desired.set((uv[0] - 0.5) * size.width * 0.72, (uv[1] - 0.5) * size.height * 0.72, 0);
    orbit.target.lerp(desired, 0.08);
  });
  return null;
}

function FpsCounter({
  fpsRef,
  frames,
  last,
}: {
  fpsRef: RefObject<HTMLSpanElement | null>;
  frames: MutableRefObject<number>;
  last: MutableRefObject<number>;
}) {
  useFrame(() => {
    frames.current += 1;
    const now = performance.now();
    if (now - last.current > 1000) {
      if (fpsRef.current) fpsRef.current.textContent = String(frames.current);
      frames.current = 0;
      last.current = now;
    }
  });
  return null;
}

export function asset(path: string) {
  return fileUrl(path);
}
