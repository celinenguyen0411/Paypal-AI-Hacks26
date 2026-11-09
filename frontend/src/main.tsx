import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { MapExperience } from "./features/map";

createRoot(document.getElementById("root") as HTMLElement).render(
  <StrictMode>
    <MapExperience />
  </StrictMode>,
);
