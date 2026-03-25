// Licensed to the .NET Foundation under one or more agreements.
// The .NET Foundation licenses this file to you under the MIT license.

using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using IniParser.Model;
using Kotor.NET.Common.Creature;
using Kotor.NET.Patcher.Exceptions;
using Kotor.NET.Extensions;
using Kotor.NET.Formats.KotorSSF;
using Kotor.NET.Patcher.Modifiers.ForSSF;
using Kotor.NET.Patcher.Modifiers.ForSSF.Values;

namespace Kotor.NET.Patcher.Parsers.LegacyINI
{
    public class SSFSectionParser
    {
        private IniData _ini;
        private KeyDataCollection _section;

        public SSFSectionParser(IniData ini, KeyDataCollection section)
        {
            _ini = ini;
            _section = section;
        }

        public List<IModifier<SSF>> Parse()
        {
            var modifiers = new List<IModifier<SSF>>();

            foreach (var section in _section)
            {
                var sound = GetSoundFromString(section.KeyName);
                var stringref = GetValueFromString(section.Value);
                modifiers.Add(new EditEntrySSFModifier(sound, stringref));
            }

            return modifiers;
        }

        private CreatureSound GetSoundFromString(string text)
        {
            if (text.EqualsIgnoreCase("Battlecry 1")) return CreatureSound.BATTLE_CRY_1;
            else if(text.EqualsIgnoreCase("Battlecry 2")) return CreatureSound.BATTLE_CRY_2;
            else if(text.EqualsIgnoreCase("Battlecry 3")) return CreatureSound.BATTLE_CRY_3;
            else if(text.EqualsIgnoreCase("Battlecry 4")) return CreatureSound.BATTLE_CRY_4;
            else if(text.EqualsIgnoreCase("Battlecry 5")) return CreatureSound.BATTLE_CRY_5;
            else if(text.EqualsIgnoreCase("Battlecry 6")) return CreatureSound.BATTLE_CRY_6;
            else if(text.EqualsIgnoreCase("Selected 1")) return CreatureSound.SELECT_1;
            else if(text.EqualsIgnoreCase("Selected 2")) return CreatureSound.SELECT_2;
            else if(text.EqualsIgnoreCase("Selected 3")) return CreatureSound.SELECT_3;
            else if(text.EqualsIgnoreCase("Attack 1")) return CreatureSound.ATTACK_GRUNT_1;
            else if(text.EqualsIgnoreCase("Attack 2")) return CreatureSound.ATTACK_GRUNT_2;
            else if(text.EqualsIgnoreCase("Attack 3")) return CreatureSound.ATTACK_GRUNT_3;
            else if(text.EqualsIgnoreCase("Pain 1")) return CreatureSound.PAIN_GRUNT_1;
            else if(text.EqualsIgnoreCase("Pain 2")) return CreatureSound.PAIN_GRUNT_2;
            else if(text.EqualsIgnoreCase("Low health")) return CreatureSound.LOW_HEALTH;
            else if(text.EqualsIgnoreCase("Death")) return CreatureSound.DEAD;
            else if(text.EqualsIgnoreCase("Critical hit")) return CreatureSound.CRITICAL_HIT;
            else if(text.EqualsIgnoreCase("Target immune")) return CreatureSound.TARGET_IMMUNE;
            else if(text.EqualsIgnoreCase("Place mine")) return CreatureSound.LAY_MINE;
            else if(text.EqualsIgnoreCase("Disarm mine")) return CreatureSound.DISARM_MINE;
            else if(text.EqualsIgnoreCase("Stealth on")) return CreatureSound.BEGIN_STEALTH;
            else if(text.EqualsIgnoreCase("Search")) return CreatureSound.BEGIN_SEARCH;
            else if(text.EqualsIgnoreCase("Pick lock start")) return CreatureSound.BEGIN_UNLOCK;
            else if(text.EqualsIgnoreCase("Pick lock fail")) return CreatureSound.UNLOCK_FAILED;
            else if(text.EqualsIgnoreCase("Pick lock done")) return CreatureSound.UNLOCK_SUCCEEDED;
            else if(text.EqualsIgnoreCase("Leave party")) return CreatureSound.SEPARATED_FROM_PARTY;
            else if(text.EqualsIgnoreCase("Rejoin party")) return CreatureSound.REJOINED_PARTY;
            else if(text.EqualsIgnoreCase("Poisoned")) return CreatureSound.POISONED;
            else throw new PatchingParserException("Unrecognized SSF creature sound.");
        }

        private IValue GetValueFromString(string text)
        {
            if (text.StartsWith("2DAMEMORY"))
            {
                int number;
                var isValidNumber = int.TryParse(text.Substring(9), out number);
                if (isValidNumber)
                {
                    return new TwoDAMemoryValue(number);
                }
                else
                {
                    throw new PatchingParserException($"2DAMEMORY{number}' with value '{text}' is not a valid StrRef.");
                }
            }
            else if (text.StartsWith("StrRef"))
            {
                int number;
                var isValidNumber = int.TryParse(text.Substring(6), out number);
                if (isValidNumber)
                {
                    return new TLKMemoryValue(number);
                }
                else
                {
                    throw new PatchingParserException($"StrRef{number}' with value '{text}' is not a valid StrRef.");
                }
            }
            else
            {
                int number;
                var isValidNumber = int.TryParse(text, out number);
                if (isValidNumber)
                {
                    return new StringRefValue(number);
                }
                else
                {
                    throw new PatchingParserException($"'{text}' is not a valid StrRef.");
                }
            }
        }
    }
}
