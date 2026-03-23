using Kotor.NET.Common.Data;
using Kotor.NET.ResourceContainers;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Common
{
    /// <summary>
    /// A class designed to centralize fetching resources from a specified installation
    /// of the games.
    /// </summary>
    public class Installation
    {
        public KotorPath GamePath { get; private set; }
        public Chitin Chitin { get; private set; }
        public KotorPath ChitinPath { get; private set; }
        public TalkTable TalkTable { get; private set; }
        public KotorPath TalkTablePath { get; private set; }
        public CapsuleFolder Modules { get; private set; }
        public KotorPath ModulesPath { get; private set; }
        public CapsuleFolder Rims { get; private set; }
        public KotorPath RimsPath { get; private set; }
        public CapsuleFolder Lips { get; private set; }
        public KotorPath LipsPath { get; private set; }
        public Capsule TexturesHigh { get; private set; }
        public Capsule TexturesMed { get; private set; }
        public Capsule TexturesLow { get; private set; }
        public Capsule TexturesGUI { get; private set; }
        public KotorPath TexturePacksPath { get; private set; }
        public ResourceFolder Override { get; private set; }
        public KotorPath OverridePath { get; private set; }
        public ResourceFolder Music { get; private set; }
        public KotorPath MusicPath { get; private set; }
        public ResourceFolder Sounds { get; private set; }
        public KotorPath SoundsPath { get; private set; }
        public ResourceFolder Voices { get; private set; }
        public KotorPath VoicesPath { get; private set; }

        public Installation(string gameDirectory)
        {
            // TODO - path handling
            GamePath = gameDirectory;

            ChitinPath = GamePath.Join("chitin.key");
            Chitin = new Chitin(gameDirectory);

            TalkTablePath = GamePath.Join("dialog.tlk");
            TalkTable = new TalkTable(TalkTablePath);

            ModulesPath = GamePath.Join("modules");
            Modules = new CapsuleFolder(ModulesPath);

            RimsPath = GamePath.Join("rims");
            Rims = new CapsuleFolder(RimsPath);

            LipsPath = GamePath.Join("lips");
            Lips = new CapsuleFolder(LipsPath);

            TexturePacksPath = gameDirectory + "TexturePacks/";
            TexturesLow = new Capsule(TexturePacksPath.Join("/swpc_tex_tpc.erf"));
            TexturesMed = new Capsule(TexturePacksPath.Join("/swpc_tex_tpb.erf"));
            TexturesHigh = new Capsule(TexturePacksPath.Join("/swpc_tex_tpa.erf"));
            TexturesGUI = new Capsule(TexturePacksPath.Join("/swpc_tex_gui.erf"));

            OverridePath = GamePath.Join("override");
            Override = new ResourceFolder(OverridePath);

            MusicPath = GamePath.Join("streammusic");
            Music = new ResourceFolder(MusicPath);

            SoundsPath = GamePath.Join("streamsounds");
            Sounds = new ResourceFolder(SoundsPath);

            VoicesPath = GamePath.Join("streamwaves");
            Voices = new ResourceFolder(VoicesPath);
        }
    }
}
