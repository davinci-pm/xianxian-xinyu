import Image from "next/image";
import { displayPersonaName, featuredPortraits, personaMarks } from "@/lib/persona-visual";

interface CharacterArtProps {
  slug: string;
  name: string;
  priority?: boolean;
  variant?: "card" | "hero" | "avatar" | "mini";
}

export default function CharacterArt({ slug, name, priority = false, variant = "card" }: CharacterArtProps) {
  const src = featuredPortraits[slug];
  const shortName = displayPersonaName(name);

  return (
    <div className={`character-art character-art-${variant} art-${slug}`}>
      {src ? (
        <Image
          alt={`${shortName}的人物肖像`}
          fill
          priority={priority}
          sizes={variant === "hero" ? "(max-width: 760px) 92vw, 48vw" : variant === "avatar" || variant === "mini" ? "160px" : "(max-width: 760px) 78vw, 360px"}
          src={src}
        />
      ) : (
        <div className="character-monogram" aria-hidden="true">
          <span>{shortName.slice(0, 1)}</span>
          <small>{personaMarks[slug] ?? "思"}</small>
        </div>
      )}
    </div>
  );
}
