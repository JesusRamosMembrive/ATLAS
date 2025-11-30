/**
 * Slash Command Menu Component
 *
 * Displays a dropdown menu of available slash commands when the user types "/"
 * as the first character in the input field. Supports filtering and keyboard navigation.
 */

import { useEffect, useRef, useCallback, useState } from "react";
import { type SlashCommand } from "../stores/claudeSessionStore";
import { ChevronRightIcon } from "./icons/AgentIcons";

interface SlashCommandMenuProps {
  /** List of available slash commands */
  commands: SlashCommand[];
  /** Current filter text (what user typed after /) */
  filter: string;
  /** Called when a command is selected */
  onSelect: (command: SlashCommand) => void;
  /** Called when menu should be closed */
  onClose: () => void;
  /** Position of the menu relative to input */
  position?: { top: number; left: number };
  /** Whether the menu is visible */
  visible: boolean;
}

export function SlashCommandMenu({
  commands,
  filter,
  onSelect,
  onClose,
  position,
  visible,
}: SlashCommandMenuProps) {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const menuRef = useRef<HTMLDivElement>(null);
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);

  // Filter commands based on user input
  const filteredCommands = commands.filter((cmd) => {
    const searchTerm = filter.toLowerCase();
    return (
      cmd.command.toLowerCase().includes(searchTerm) ||
      cmd.label.toLowerCase().includes(searchTerm) ||
      cmd.description.toLowerCase().includes(searchTerm)
    );
  });

  // Reset selected index when filter changes
  useEffect(() => {
    setSelectedIndex(0);
  }, [filter]);

  // Scroll selected item into view
  useEffect(() => {
    if (itemRefs.current[selectedIndex]) {
      itemRefs.current[selectedIndex]?.scrollIntoView({
        block: "nearest",
        behavior: "smooth",
      });
    }
  }, [selectedIndex]);

  // Handle keyboard navigation
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (!visible) return;

      switch (e.key) {
        case "ArrowDown":
          e.preventDefault();
          setSelectedIndex((prev) =>
            prev < filteredCommands.length - 1 ? prev + 1 : 0
          );
          break;
        case "ArrowUp":
          e.preventDefault();
          setSelectedIndex((prev) =>
            prev > 0 ? prev - 1 : filteredCommands.length - 1
          );
          break;
        case "Enter":
        case "Tab":
          e.preventDefault();
          if (filteredCommands[selectedIndex]) {
            onSelect(filteredCommands[selectedIndex]);
          }
          break;
        case "Escape":
          e.preventDefault();
          onClose();
          break;
      }
    },
    [visible, filteredCommands, selectedIndex, onSelect, onClose]
  );

  // Add keyboard listener
  useEffect(() => {
    if (visible) {
      window.addEventListener("keydown", handleKeyDown);
      return () => window.removeEventListener("keydown", handleKeyDown);
    }
  }, [visible, handleKeyDown]);

  // Close on click outside
  useEffect(() => {
    if (!visible) return;

    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [visible, onClose]);

  if (!visible || filteredCommands.length === 0) {
    return null;
  }

  return (
    <div
      ref={menuRef}
      className="slash-command-menu"
      style={
        position
          ? {
              bottom: position.top,
              left: position.left,
            }
          : undefined
      }
      role="listbox"
      aria-label="Slash commands"
    >
      <div className="slash-command-header">
        <span className="slash-command-title">Commands</span>
        <span className="slash-command-hint">↑↓ navigate • Enter select • Esc close</span>
      </div>
      <div className="slash-command-list">
        {filteredCommands.map((cmd, index) => (
          <button
            key={cmd.command}
            ref={(el) => (itemRefs.current[index] = el)}
            className={`slash-command-item ${index === selectedIndex ? "selected" : ""}`}
            onClick={() => onSelect(cmd)}
            onMouseEnter={() => setSelectedIndex(index)}
            role="option"
            aria-selected={index === selectedIndex}
          >
            <div className="slash-command-main">
              <span className="slash-command-name">{cmd.command}</span>
              {cmd.hasArgs && (
                <span className="slash-command-args">{cmd.argPlaceholder}</span>
              )}
            </div>
            <span className="slash-command-description">{cmd.description}</span>
            <span className="slash-command-arrow" aria-hidden="true">
              <ChevronRightIcon size={12} />
            </span>
          </button>
        ))}
      </div>
      {filteredCommands.length === 0 && (
        <div className="slash-command-empty">
          No commands matching "{filter}"
        </div>
      )}
    </div>
  );
}

// CSS styles for the component
export const slashCommandMenuStyles = `
/* Slash Command Menu */
.slash-command-menu {
  position: absolute;
  bottom: 100%;
  left: 0;
  right: 0;
  max-height: 300px;
  background: var(--agent-bg-secondary);
  border: 1px solid var(--agent-border-secondary);
  border-radius: 8px;
  box-shadow: 0 -4px 20px var(--agent-shadow);
  overflow: hidden;
  z-index: 1000;
  margin-bottom: 8px;
}

.slash-command-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: var(--agent-bg-tertiary);
  border-bottom: 1px solid var(--agent-border-primary);
}

.slash-command-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--agent-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.slash-command-hint {
  font-size: 10px;
  color: var(--agent-text-muted);
}

.slash-command-list {
  max-height: 250px;
  overflow-y: auto;
  padding: 4px;
}

.slash-command-list::-webkit-scrollbar {
  width: 6px;
}

.slash-command-list::-webkit-scrollbar-track {
  background: var(--agent-bg-secondary);
}

.slash-command-list::-webkit-scrollbar-thumb {
  background: var(--agent-border-secondary);
  border-radius: 3px;
}

.slash-command-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  width: 100%;
  padding: 10px 12px;
  background: transparent;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
  text-align: left;
  position: relative;
}

.slash-command-item:hover,
.slash-command-item.selected {
  background: var(--agent-bg-tertiary);
}

.slash-command-item.selected {
  outline: 1px solid var(--agent-accent-blue);
}

.slash-command-main {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 2px;
}

.slash-command-name {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  font-weight: 500;
  color: var(--agent-accent-blue);
}

.slash-command-args {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: var(--agent-text-muted);
  font-style: italic;
}

.slash-command-description {
  font-size: 12px;
  color: var(--agent-text-secondary);
  line-height: 1.4;
}

.slash-command-arrow {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--agent-text-muted);
  opacity: 0;
  transition: opacity 0.15s;
}

.slash-command-item:hover .slash-command-arrow,
.slash-command-item.selected .slash-command-arrow {
  opacity: 1;
}

.slash-command-empty {
  padding: 16px;
  text-align: center;
  color: var(--agent-text-muted);
  font-size: 12px;
}

/* Mobile adjustments */
@media (max-width: 480px) {
  .slash-command-menu {
    max-height: 200px;
  }

  .slash-command-header {
    padding: 6px 10px;
  }

  .slash-command-hint {
    display: none;
  }

  .slash-command-item {
    padding: 8px 10px;
  }

  .slash-command-name {
    font-size: 12px;
  }

  .slash-command-description {
    font-size: 11px;
  }
}
`;
