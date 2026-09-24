// @met4citizen/talkinghead ships plain .mjs with no type declarations.
// This is a minimal ambient typing for the subset of the API FaceStageCanvas uses.
// See https://github.com/met4citizen/TalkingHead for the full API.
declare module "@met4citizen/talkinghead" {
  export interface ShowAvatarOptions {
    url: string;
    body?: "M" | "F";
    avatarMood?: string;
    lipsyncLang?: string;
    [key: string]: unknown;
  }

  export interface SpeakAudioInput {
    audio: AudioBuffer | ArrayBuffer[];
    words?: string[];
    wtimes?: number[];
    wdurations?: number[];
    visemes?: string[];
    vtimes?: number[];
    vdurations?: number[];
    [key: string]: unknown;
  }

  export interface TalkingHeadOptions {
    lipsyncModules?: string[];
    lipsyncLang?: string;
    modelPixelRatio?: number;
    modelFPS?: number;
    cameraView?: "full" | "mid" | "upper" | "head";
    avatarMood?: string;
    avatarMute?: boolean;
    [key: string]: unknown;
  }

  export class TalkingHead {
    constructor(node: HTMLElement, opt?: TalkingHeadOptions);
    showAvatar(
      avatar: ShowAvatarOptions,
      onprogress?: ((event: ProgressEvent) => void) | null
    ): Promise<void>;
    speakText(text: string, opt?: Record<string, unknown>): void;
    speakAudio(
      audio: SpeakAudioInput,
      opt?: Record<string, unknown>,
      onsubtitles?: ((subtitle: string) => void) | null
    ): void;
    setFixedValue(name: string, value: number | null): void;
    setView(view: "full" | "mid" | "upper" | "head", opt?: Record<string, unknown>): void;
  }
}
