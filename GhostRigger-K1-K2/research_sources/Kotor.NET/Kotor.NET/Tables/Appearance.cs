using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Tables
{
    public class Appearance
    {
        public string Label { get; set; }
        public string Race { get; set; }
        public float WalkDist { get; set; }
        public float RunDist { get; set; }
        public float DriveAnimWalk { get; set; }
        public float DriveAnimRun { get; set; }
        public string RaceTex { get; set; }
        public ModelType modelType { get; set; }
        public int NormalHead { get; set; }
        public int BackupHeader { get; set; }
        public string EnvMap { get; set; }
        public BloodColor BloodColor { get; set; }
        public float WeaponScale { get; set; }
        public float WingTailScale { get; set; }
        public MoveRate MoveRate { get; set; }
        public int DriveAcceleration { get; set; }
        public float DriveMaxSpeed { get; set; }
        public float HitRadius { get; set; }
        public float PerceptionSpace { get; set; }
        public float CreaturePerceptionSpace { get; set; }
        public string CameraSpace { get; set; }
        public float Height { get; set; }
        public string TargetHeight { get; set; }
        public bool AbortOnParry { get; set; }
        public int RacialType { get; set; }
        public bool HasLegs { get; set; }
        public bool HasArms { get; set; }
        public string Portrait { get; set; }
        public string FootstepSound { get; set; }
        public float FootstepVolume { get; set; }
        /// <summary>
        /// An index to creaturesize.2da.
        /// </summary>
        public int SizeCategoryID { get; set; }
        /// <summary>
        /// An index into ranges.2da
        /// </summary>
        public int PerceptionDistanceID { get; set; }
        /// <summary>
        /// An index into footstepsounds.2da
        /// </summary>
        public int FootstepDistanceID { get; set; }
        /// <summary>
        /// An index into footstepsounds.2da.
        /// </summary>
        public int FootstepTypeID { get; set; }
        /// <summary>
        /// An index into appearancesndset.2da.
        /// </summary>
        public int SoundAppTypeID { get; set; }
        bool HeadTrack { get; set; }
        public int HeadMaxHorizontalArc { get; set; }
        public int HeadMaxVerticalArc { get; set; }
        /// <summary>
        /// Unusued?
        /// </summary>
        public string HeadBone { get; set; }



        public int StringRef { get; set; }
    }

    public enum ModelType
    {

    }

    public enum BloodColor
    {

    }

    public enum MoveRate
    {

    }
}
