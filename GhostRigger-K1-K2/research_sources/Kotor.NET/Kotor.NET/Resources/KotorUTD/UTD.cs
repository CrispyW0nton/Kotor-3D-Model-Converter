using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Data;

namespace Kotor.NET.Resources.KotorUTD
{
    public class UTD
    {
        public byte AnimationState { get; set; }
        public uint Appearance { get; set; }
        public byte AutoRemoveKey { get; set; }
        public byte CloseLockDC { get; set; }
        public string Comment { get; set; } = "";
        public ResRef Conversation { get; set; } = "";
        public short CurrentHP { get; set; }
        public LocalizedString Description { get; set; } = new();
        public byte DisarmDC { get; set; }
        public uint Faction { get; set; }
        public byte Fort { get; set; }
        public byte GenericType { get; set; }
        public byte Hardness { get; set; }
        public short HP { get; set; }
        public byte Interruptable { get; set; }
        public string KeyName { get; set; } = "";
        public byte KeyRequired { get; set; }
        public ushort LoadScreenID { get; set; }
        public byte Lockable { get; set; }
        public byte Locked { get; set; }
        public LocalizedString LocName { get; set; } = new();
        public byte Min1HP { get; set; }
        public ResRef OnClick { get; set; } = "";
        public ResRef OnClosed { get; set; } = "";
        public ResRef OnDamaged { get; set; } = "";
        public ResRef OnDeath { get; set; } = "";
        public ResRef OnDisarm { get; set; } = "";
        public ResRef OnFailToOpen { get; set; } = "";
        public ResRef OnHeartbeat { get; set; } = "";
        public ResRef OnLock { get; set; } = "";
        public ResRef OnMeleeAttacked { get; set; } = "";
        public ResRef OnOpen { get; set; } = "";
        public ResRef OnSpellCastAt { get; set; } = "";
        public ResRef OnTrapTriggered { get; set; } = "";
        public ResRef OnUnlock { get; set; } = "";
        public ResRef OnUserDefined { get; set; } = "";
        public byte OpenLockDC { get; set; }
        public byte OpenLockDiff { get; set; }
        public sbyte OpenLockDiffMod { get; set; }
        public byte OpenState { get; set; }
        public byte PaletteID { get; set; }
        public byte Plot { get; set; }
        public ushort PortraitId { get; set; }
        public byte Ref { get; set; }
        public byte Static { get; set; }
        public string Tag { get; set; } = "";
        public ResRef TemplateResRef { get; set; } = "";
        public byte TrapDetectable { get; set; }
        public byte TrapDetectDC { get; set; }
        public byte TrapDisarmable { get; set; }
        public byte TrapFlag { get; set; }
        public byte TrapOneShot { get; set; }
        public byte TrapType { get; set; }
        public byte Will { get; set; }
        public byte NotBlastable { get; set; }
    }
}
