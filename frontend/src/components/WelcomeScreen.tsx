import React, { useState, useEffect } from "react";
import { InputForm } from "./InputForm";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface WelcomeScreenProps {
  handleSubmit: (
    submittedInputValue: string,
    effort: string,
    model: string
  ) => void;
  onCancel: () => void;
  isLoading: boolean;
}

const translations = {
  en: {
    welcome: "Welcome.",
    helpText: "How can I help you today?",
    poweredBy: "Powered by Google Gemini and LangChain LangGraph.",
  },
  "zh-TW": {
    welcome: "歡迎。",
    helpText: "請問有什麼可以幫您？",
    poweredBy: "由 Google Gemini 和 LangChain LangGraph 強力驅動。",
  },
  ja: {
    welcome: "ようこそ。",
    helpText: "何かお手伝いできることはありますか？",
    poweredBy: "Google Gemini と LangChain LangGraph を搭載しています。",
  },
};

export const WelcomeScreen: React.FC<WelcomeScreenProps> = ({
  handleSubmit,
  onCancel,
  isLoading,
}) => {
  const [currentLanguage, setCurrentLanguage] = useState("en");

  useEffect(() => {
    document.documentElement.lang = currentLanguage;
  }, [currentLanguage]);

  const t = translations[currentLanguage as keyof typeof translations];

  return (
    <div className="flex flex-col items-center justify-center text-center px-4 flex-1 w-full max-w-3xl mx-auto gap-4">
      <div className="absolute top-4 right-4">
        <Select
          value={currentLanguage}
          onValueChange={(value) => setCurrentLanguage(value)}
        >
          <SelectTrigger className="w-[120px] bg-neutral-700 border-neutral-600 text-neutral-300 focus:ring-sky-500">
            <SelectValue placeholder="Language" />
          </SelectTrigger>
          <SelectContent className="bg-neutral-700 border-neutral-600 text-neutral-300">
            <SelectItem value="en" className="focus:bg-sky-600 focus:text-neutral-100">English</SelectItem>
            <SelectItem value="zh-TW" className="focus:bg-sky-600 focus:text-neutral-100">繁體中文</SelectItem>
            <SelectItem value="ja" className="focus:bg-sky-600 focus:text-neutral-100">日本語</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div>
        <h1 className="text-5xl md:text-6xl font-semibold text-neutral-100 mb-3">
          {t.welcome}
        </h1>
        <p className="text-xl md:text-2xl text-neutral-400">
          {t.helpText}
        </p>
      </div>
      <div className="w-full mt-4">
        <InputForm
          onSubmit={handleSubmit}
          isLoading={isLoading}
          onCancel={onCancel}
          hasHistory={false}
        />
      </div>
      <p className="text-xs text-neutral-500">{t.poweredBy}</p>
    </div>
  );
};
