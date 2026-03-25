using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Data;
using Kotor.NET.Common.Item;

namespace Kotor.NET.Resources.KotorUTP
{
    public class UTP
    {
        public Byte AnimationState { get; set; }
        public UInt32 Appearance { get; set; }
        public Byte AutoRemoveKey { get; set; }
        public Byte BodyBag { get; set; }
        public Byte CloseLockDC { get; set; }
        public String Comment { get; set; } = "";
        public ResRef Conversation { get; set; } = "";
        public Int16 CurrentHP { get; set; }
        public LocalizedString Description { get; set; } = new();
        public Byte DisarmDC { get; set; }
        public UInt32 Faction { get; set; }
        public Byte Fort { get; set; }
        public Byte Hardness { get; set; }
        public Byte HasInventory { get; set; }
        public Int16 HP { get; set; }
        public Byte Interruptable { get; set; }
        public Byte IsComputer { get; set; }
        public String KeyName { get; set; } = "";
        public Byte KeyRequired { get; set; }
        public Byte Lockable { get; set; }
        public Byte Locked { get; set; }
        public LocalizedString LocName { get; set; } = new();
        public Byte Min1HP { get; set; }
        public Byte NotBlastable { get; set; }
        public ResRef OnClosed { get; set; } = "";
        public ResRef OnDamaged { get; set; } = "";
        public ResRef OnDeath { get; set; } = "";
        public ResRef OnDisarm { get; set; } = "";
        public ResRef OnEndDialogue { get; set; } = "";
        public ResRef OnFailToOpen { get; set; } = "";
        public ResRef OnHeartbeat { get; set; } = "";
        public ResRef OnInvDisturbed { get; set; } = "";
        public ResRef OnLock { get; set; } = "";
        public ResRef OnMeleeAttacked { get; set; } = "";
        public ResRef OnOpen { get; set; } = "";
        public ResRef OnSpellCastAt { get; set; } = "";
        public ResRef OnTrapTriggered { get; set; } = "";
        public ResRef OnUnlock { get; set; } = "";
        public ResRef OnUsed { get; set; } = "";
        public ResRef OnUserDefined { get; set; } = "";
        public Byte OpenLockDC { get; set; }
        public Byte OpenLockDiff { get; set; }
        public SByte OpenLockDiffMod { get; set; }
        public Byte PaletteID { get; set; }
        public Byte PartyInteract { get; set; }
        public Byte Plot { get; set; }
        public UInt16 PortraitId { get; set; }
        public Byte Ref { get; set; }
        public Byte Static { get; set; }
        public String Tag { get; set; } = "";
        public ResRef TemplateResRef { get; set; } = "";
        public Byte TrapDetectable { get; set; }
        public Byte TrapDetectDC { get; set; }
        public Byte TrapDisarmable { get; set; }
        public Byte TrapFlag { get; set; }
        public Byte TrapOneShot { get; set; }
        public Byte TrapType { get; set; }
        public Byte Type { get; set; }
        public Byte Useable { get; set; }
        public Byte Will { get; set; }
        public List<StoredItem> Inventory { get; set; } = new();
    }
}
