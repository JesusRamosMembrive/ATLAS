"use client";
import { useEffect, useState, useId } from "react";
import Particles, { initParticlesEngine } from "@tsparticles/react";
import type { Container } from "@tsparticles/engine";
import { loadSlim } from "@tsparticles/slim";
import clsx from "clsx";

export interface SparklesCoreProps {
  id?: string;
  className?: string;
  background?: string;
  minSize?: number;
  maxSize?: number;
  speed?: number;
  particleColor?: string;
  particleDensity?: number;
}

export function SparklesCore({
  id,
  className,
  background = "transparent",
  minSize = 0.4,
  maxSize = 1.4,
  speed = 1,
  particleColor = "#60a5fa",
  particleDensity = 120,
}: SparklesCoreProps) {
  const [init, setInit] = useState(false);
  const generatedId = useId();

  useEffect(() => {
    initParticlesEngine(async (engine) => {
      await loadSlim(engine);
    }).then(() => {
      setInit(true);
    });
  }, []);

  const particlesLoaded = async (container?: Container) => {
    // Container loaded
  };

  if (!init) {
    return null;
  }

  return (
    <Particles
      id={id ?? generatedId}
      className={clsx("sparkles-container", className)}
      particlesLoaded={particlesLoaded}
      options={{
        background: {
          color: {
            value: background,
          },
        },
        fullScreen: {
          enable: false,
          zIndex: 0,
        },
        fpsLimit: 60,
        interactivity: {
          events: {
            onClick: {
              enable: false,
            },
            onHover: {
              enable: false,
            },
          },
        },
        particles: {
          color: {
            value: particleColor,
          },
          links: {
            enable: false,
          },
          move: {
            direction: "none",
            enable: true,
            outModes: {
              default: "bounce",
            },
            random: true,
            speed: speed,
            straight: false,
          },
          number: {
            density: {
              enable: true,
              height: 400,
              width: 400,
            },
            value: particleDensity,
          },
          opacity: {
            value: {
              min: 0.1,
              max: 1,
            },
            animation: {
              enable: true,
              speed: 1,
              startValue: "random",
              sync: false,
            },
          },
          shape: {
            type: "circle",
          },
          size: {
            value: {
              min: minSize,
              max: maxSize,
            },
            animation: {
              enable: true,
              speed: 2,
              startValue: "random",
              sync: false,
            },
          },
        },
        detectRetina: true,
      }}
    />
  );
}
