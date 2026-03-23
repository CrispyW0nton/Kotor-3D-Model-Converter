using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Creature;
using Kotor.NET.Common.Data;
using Kotor.NET.Common.Item;

namespace Kotor.NET.Resources.KotorUTC
{
    public class UTC
    {
        public ResRef ResRef { get; set; }
        public ResRef Conversation { get; set; }

        public string Tag { get; set; }
        public string Comment { get; set; }

        public LocalizedString FirstName { get; set; }
        public LocalizedString LastName { get; set; }

        public byte RaceID { get; set; }
        public byte SubraceID { get; set; }
        public ushort PortraitID { get; set; }
        public byte PerceptionID { get; set; }
        public ushort AppearanceID { get; set; }
        public byte GenderID { get; set; }
        public ushort FactionID { get; set; }
        public int WalkRateID { get; set; }
        public ushort SoundsetID { get; set; }
        /// <summary>
        /// Used by the toolset.
        /// </summary>
        public byte PaletteID { get; set; }

        public byte BodyVariation { get; set; }
        public byte TextureVariation { get; set; }

        public bool NotReorientating { get; set; }
        public bool PartyInteract { get; set; }
        public bool NoPermanentDeath { get; set; }
        public bool Min1HP { get; set; }
        public bool Plot { get; set; }
        public bool Interruptable { get; set; }
        public bool IsPC { get; set; }
        public bool Disarmable { get; set; }
        public bool IgnoreCreaturePath { get; set; }
        public bool Hologram { get; set; }

        public int Alignment { get; set; }

        public float ChallengeRating { get; set; }
        public float Blindspot { get; set; }
        public float MultiplierSet { get; set; }

        public byte NaturalAC { get; set; }
        public short ReflexBonus { get; set; }
        public short WillBonus { get; set; }
        public short FortitudeBonus { get; set; }

        public short HP { get; set; }
        public short CurrentHP { get; set; }
        public short MaxHP { get; set; }

        public short FP { get; set; }
        public short MaxFP { get; set; }

        public byte ComputerUse { get; set; }
        public byte Demolitions { get; set; }
        public byte Stealth { get; set; }
        public byte Awareness { get; set; }
        public byte Persuade { get; set; }
        public byte Repair { get; set; }
        public byte Security { get; set; }
        public byte TreatInjury { get; set; }

        public byte Strength { get; set; }
        public byte Dexterity { get; set; }
        public byte Constitution { get; set; }
        public byte Intelligence { get; set; }
        public byte Wisdom { get; set; }
        public byte Charisma { get; set; }


        public ResRef OnEndDialog { get; set; } = "";
        public ResRef OnBlocked { get; set; } = "";
        public ResRef OnHeartbeat { get; set; } = "";
        public ResRef OnNotice { get; set; } = "";
        public ResRef OnSpell { get; set; } = "";
        public ResRef OnAttack { get; set; } = "";
        public ResRef OnDamaged { get; set; } = "";
        public ResRef OnDisturbed { get; set; } = "";
        public ResRef OnEndRound { get; set; } = "";
        public ResRef OnDialog { get; set; } = "";
        public ResRef OnSpawn { get; set; } = "";
        public ResRef OnRested { get; set; } = "";
        public ResRef OnDeath { get; set; } = "";
        public ResRef OnUserDefined { get; set; } = "";

        public List<Class> Classes { get; set; } = new();
        public List<Feat> Feats { get; set; } = new();
        public List<StoredItem> Inventory { get; set; } = new();
        public List<EquippedItem> Equipment { get; set; } = new();

        /// <summary>
        /// Deprecated property of UTCs. Body bags for creatures are determined by
        /// the appearance.2da file.
        /// </summary>
        public byte BodyBagID { get; set; }
        public string Deity { get; set; } = "";
        public LocalizedString Description { get; set; } = new();
        public byte Lawfulness { get; set; }
        public int PhenotypeID { get; set; }
        public string SubraceName { get; set; } = "";
    }
}
