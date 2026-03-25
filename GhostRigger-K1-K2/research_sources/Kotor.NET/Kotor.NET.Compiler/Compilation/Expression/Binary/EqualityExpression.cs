using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Formats.KotorNCS;

namespace Kotor.NET.Scripting.Compilation.Expression.Binary
{
    public class EqualityExpression : IExpression
    {
        public IExpression LHS { get; set; }
        public IExpression RHS { get; set; }

        public EqualityExpression(IExpression lhs, IExpression rhs)
        {
            LHS = lhs;
            RHS = rhs;
        }

        public DataType GetDataType()
        {
            return DataType.Float;
        }

        public void Compile(SymbolTable symbolTable, NCS ncs)
        {
            LHS.Compile(symbolTable, ncs);
            RHS.Compile(symbolTable, ncs);

            var lhs = LHS.GetDataType();
            var rhs = RHS.GetDataType();

            if (lhs == DataType.Int && rhs == DataType.Int)
            {
                ncs.Add(new NCSInstruction.EQUALII());
            }
            else if (lhs == DataType.Float && rhs == DataType.Float)
            {
                ncs.Add(new NCSInstruction.EQUALFF());
            }
            else if (lhs == DataType.String && rhs == DataType.String)
            {
                ncs.Add(new NCSInstruction.EQUALSS());
            }
            else if (lhs == DataType.Object && rhs == DataType.Object)
            {
                ncs.Add(new NCSInstruction.EQUALOO());
            }
            else if (lhs == DataType.Effect && rhs == DataType.Effect)
            {
                ncs.Add(new NCSInstruction.EQUALEFFEFF());
            }
            else if (lhs == DataType.Event && rhs == DataType.Event)
            {
                ncs.Add(new NCSInstruction.EQUALEVTEVT());
            }
            else if (lhs == DataType.Talent && rhs == DataType.Talent)
            {
                ncs.Add(new NCSInstruction.EQUALTALTAL());
            }
            else if (lhs == DataType.Location && rhs == DataType.Location)
            {
                ncs.Add(new NCSInstruction.EQUALLOCLOC());
            }
            // STRUCT?
            //else if (lhs == DataType. && rhs == DataType.Location)
            //{
            //    ncs.Add(new NCSInstruction.EQUALTT());
            //}
            else
            {
                throw new NotImplementedException();
            }
        }
    }
}
